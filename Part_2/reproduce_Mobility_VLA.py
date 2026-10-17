import os
import re
import cv2
import tqdm
import numpy as np
import networkx as nx
from PIL import Image
from moviepy import VideoFileClip
import google.generativeai as genai
from pytubefix import YouTube
import matplotlib.pyplot as plt

def download_tour_video(url="https://www.youtube.com/watch?v=C_jSIKC1OyY", output_path="video.mp4"):
        print("Downloading tour video")
        yt = YouTube(url)
        stream = yt.streams.get_by_itag(244) # 480p stream
        if not stream:
            stream = yt.streams.filter(res="480p").first() # youtube may change so we need to check first
        stream.download(filename=output_path)
        return output_path

def mp4_to_pil_images(mp4_file, save_every_n_frames=600, img_downsample_ratio=2):
    clip = VideoFileClip(mp4_file)
    images = []
    frame_counter = 0
    for frame in tqdm.tqdm(clip.iter_frames()):
        if frame_counter % save_every_n_frames != 0:
            frame_counter += 1
            continue
        pil_image = Image.fromarray(frame[::img_downsample_ratio, ::img_downsample_ratio, :])
        images.append(pil_image)
        frame_counter += 1
    clip.close()
    return images

def get_framed_chunks_from_imgs(imgs, custom_pois=None):
    if custom_pois is None:
        custom_pois = {0: "entrance lobby", 15: "Lewis' desk", 20: "pantry and refrigerator"}
    chunks = []
    for i, img in enumerate(imgs):
        caption = f"Frame {i}."
        if i in custom_pois:
            caption = f"Frame {i}. {custom_pois[i]}."
        chunks.append(img)
        chunks.append(caption)
    return chunks

def query_high_level_vlm(gemini_model, text_model, user_query, tour_chunks):
    contents = [
        "You are a robot operating in a building and your task is to respond to the user "
        "command about going to a specific location by finding the closest frame in the tour "
        "video to navigate to. These frames are from the tour of the building last year.",
        *tour_chunks,  # Fixed paper typo '- tour_chunks'
        "The user says: ",
        user_query,
        "How would you respond? Can you find the closest frame?",
    ]
    response_stage1 = gemini_model.generate_content(contents)
    stage1_text = response_stage1.text

    clarify_prompt = [
        stage1_text,
        "Can you find only one unique frame number in the sentence above? Tell me that frame number and nothing else."
    ]
    response_stage2 = text_model.generate_content(clarify_prompt)
    
    #regex extraction
    match = re.search(r'\b\d+\b', response_stage2.text)
    goal_idx = int(match.group(0)) if match else -1
    return goal_idx, stage1_text

def visualize_navigation_results(start_idx, goal_idx, frames, path, controller, save_path="nav_result.png"):
    """
    Renders:
    1. Start Frame Image
    2. Predicted Destination Frame Image
    3. 2D Topological Map with Dijkstra Planned Path
    """
    fig = plt.figure(figsize=(14, 6))
    
    # Left subplot: Start Camera Frame
    ax1 = fig.add_subplot(1, 3, 1)
    ax1.imshow(frames[start_idx])
    ax1.set_title(f"Start View (Node {start_idx})", fontsize=12, fontweight='bold')
    ax1.axis("off")
    
    # Center subplot: Destination Camera Frame
    ax2 = fig.add_subplot(1, 3, 2)
    if 0 <= goal_idx < len(frames):
        ax2.imshow(frames[goal_idx])
        ax2.set_title(f"Predicted Goal View (Node {goal_idx})", fontsize=12, fontweight='bold', color='green')
    else:
        ax2.text(0.5, 0.5, "Invalid Goal Index", ha='center', va='center')
        ax2.set_title("Predicted Goal View (Failed)", fontsize=12, fontweight='bold', color='red')
    ax2.axis("off")
    
    # Right subplot: 2D Topological Path on Graph G
    ax3 = fig.add_subplot(1, 3, 3)
    nodes = list(controller.G.nodes())
    x_coords = [controller.poses[n][0] for n in nodes]
    y_coords = [controller.poses[n][1] for n in nodes]
    
    # Plot all topological nodes and edges
    ax3.plot(x_coords, y_coords, color='lightgray', linestyle='--', linewidth=1.5, label='Topological Graph')
    ax3.scatter(x_coords, y_coords, color='gray', s=20, alpha=0.6)
    
    # Highlight planned Dijkstra path
    if path:
        path_x = [controller.poses[n][0] for n in path]
        path_y = [controller.poses[n][1] for n in path]
        ax3.plot(path_x, path_y, color='blue', linewidth=2.5, label='Dijkstra Path')
        ax3.scatter(path_x[0], path_y[0], color='orange', s=100, zorder=5, label='Start')
        ax3.scatter(path_x[-1], path_y[-1], color='green', s=120, marker='*', zorder=5, label='Goal')

    ax3.set_title("Topological Map & Trajectory", fontsize=12, fontweight='bold')
    ax3.set_xlabel("X Position (meters)")
    ax3.set_ylabel("Y Position (meters)")
    ax3.legend(loc='upper right', fontsize=8)
    ax3.grid(True, linestyle=':', alpha=0.6)
    
    plt.tight_layout()
    plt.savefig(save_path, dpi=200)
    print(f"\n[Saved Visualization]: {save_path}")
    plt.show()

# =============================================================================
# 2. QUANTITATIVE BENCHMARK EVALUATOR
# =============================================================================
def run_quantitative_benchmark(vlm, text_vlm, frames, chunks, controller):
    """
    Evaluates representative queries across Reasoning-Free (RF) and 
    Reasoning-Required (RR) categories, reporting SR, Frame Error, and SPL.
    """
    benchmark_tasks = [
        {"cat": "RF", "query": "Take me to the entrance lobby.", "gt_frame": 0},
        {"cat": "RF", "query": "Take me to Lewis' desk.", "gt_frame": 150},
        {"cat": "RR", "query": "Where can I find something cold to drink?", "gt_frame": 192},
        {"cat": "RR", "query": "I am hungry and need to prepare lunch, take me there.", "gt_frame": 192},
    ]
    
    print("\n" + "="*80)
    print("RUNNING QUANTITATIVE BENCHMARK EVALUATION")
    print("="*80)
    
    tolerance_frames = 10  # Roughly ~5-10 meters tolerance
    results = []
    
    for task in benchmark_tasks:
        pred_idx, reasoning = query_high_level_vlm(vlm, text_vlm, task["query"], chunks)
        error = abs(pred_idx - task["gt_frame"]) if pred_idx != -1 else 999
        success = 1 if error <= tolerance_frames else 0
        
        # Calculate SPL: SPL = Success * (Shortest_Path_Length / max(Traversed_Path_Length, Shortest_Path_Length))
        if success:
            gt_path, _ = controller.generate_actions(0, task["gt_frame"])
            pred_path, _ = controller.generate_actions(0, pred_idx)
            L_optimal = len(gt_path) * 1.5
            P_actual = len(pred_path) * 1.5
            spl = 1.0 * (L_optimal / max(P_actual, L_optimal))
        else:
            spl = 0.0
            
        results.append({
            "category": task["cat"],
            "query": task["query"],
            "gt": task["gt_frame"],
            "pred": pred_idx,
            "error": error,
            "success": success,
            "spl": spl
        })
        print(f"[{task['cat']}] Query: '{task['query']}'")
        print(f"       GT: Frame {task['gt_frame']} | Pred: Frame {pred_idx} | Error: {error} frames | Status: {'PASS' if success else 'FAIL'} | SPL: {spl:.2f}")

    # Aggregated Metrics
    sr = np.mean([r["success"] for r in results]) * 100
    mean_error = np.mean([r["error"] for r in results if r["pred"] != -1])
    mean_spl = np.mean([r["spl"] for r in results])
    
    print("\n" + "="*80)
    print("FINAL QUANTITATIVE METRICS SUMMARY")
    print("="*80)
    print(f"Goal-Finding Success Rate (SR): {sr:.1f}%")
    print(f"Average Frame Localization Error: {mean_error:.1f} frames")
    print(f"Success-weighted Path Length (SPL): {mean_spl:.3f}")
    print("="*80)
    
    return results


# TOPOLOGICAL GRAPH & WAYPOINT ACTION

class TopologicalActionController:
    """Simulates the offline graph and local waypoint generator."""
    def __init__(self, num_nodes, node_spacing_meters=1.5):
        self.G = nx.DiGraph()
        self.poses = {}
        
        # Build 1D/2D topological hallway
        for i in range(num_nodes):
            x = i * node_spacing_meters
            y = 0.5 * np.sin(i * 0.3)  # Gentle corridor curve
            yaw = 0.0
            self.poses[i] = np.array([x, y, yaw])
            self.G.add_node(i, pos=self.poses[i])
            if i > 0:
                dist = np.linalg.norm(self.poses[i][:2] - self.poses[i-1][:2])
                self.G.add_edge(i - 1, i, weight=dist)
                self.G.add_edge(i, i - 1, weight=dist)

    def generate_actions(self, start_idx, goal_idx):
        path = nx.shortest_path(self.G, source=start_idx, target=goal_idx, weight="weight")
        actions = []
        for i in range(len(path) - 1):
            curr_node = path[i]
            next_node = path[i+1]
            p_curr = self.poses[curr_node]
            p_next = self.poses[next_node]
            
            # Robot-centric relative action (dx, dy, dtheta)
            dx = p_next[0] - p_curr[0]
            dy = p_next[1] - p_curr[1]
            dtheta = p_next[2] - p_curr[2]
            actions.append({"from": curr_node, "to": next_node, "waypoint": (dx, dy, dtheta)})
        return path, actions

# =============================================================================
# MAIN BENCHMARK RUNNER
# =============================================================================

if __name__ == "__main__":
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("Please set your GEMINI_API_KEY environment variable.")
        
    genai.configure(api_key=api_key)
    cfg = genai.types.GenerationConfig(temperature=0.0)
    vlm = genai.GenerativeModel("gemini-3.8-flash", generation_config=cfg)
    text_vlm = genai.GenerativeModel("gemini-3.8-flash", generation_config=cfg)

    # 1. Download & Extract Tour
    video_path = download_tour_video()
    frames = mp4_to_pil_images(video_path, save_every_n_frames=600, img_downsample_ratio=2)
    print(f"\nExtracted {len(frames)} frames at 1 Hz.")

    # 2. Build Chunks & Controller
    pois = {0: "entrance lobby", 7: "Lewis' desk", 9: "kitchen refrigerator"}
    chunks = get_framed_chunks_from_imgs(frames, pois)
    controller = TopologicalActionController(num_nodes=len(frames))

    # 3. Single Run Visualization
    start_node = 0
    query = "Where can I find something cold to drink?"
    print(f"\nExecuting Single Run: '{query}'")
    goal_idx, explanation = query_high_level_vlm(vlm, text_vlm, query, chunks)
    path, actions = controller.generate_actions(start_node, goal_idx)
    
    # Save & Display Plot
    visualize_navigation_results(start_node, goal_idx, frames, path, controller, save_path="nav_result.png")

    # 4. Run Quantitative Benchmark
    run_quantitative_benchmark(vlm, text_vlm, frames, chunks, controller)