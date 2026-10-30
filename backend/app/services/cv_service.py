import os
import uuid
from pathlib import Path
from typing import Dict, Any, Tuple
import cv2
import numpy as np
from PIL import Image

from app.config import settings

def load_image_cv(image_path: str) -> np.ndarray:
    """Safely read image into OpenCV BGR numpy array."""
    if not os.path.exists(image_path):
        raise FileNotFoundError(f"Image not found at path: {image_path}")
    # Use cv2.imdecode to support cross-platform UTF-8 filepaths on Windows
    with open(image_path, "rb") as f:
        file_bytes = np.frombuffer(f.read(), np.uint8)
        img = cv2.imdecode(file_bytes, cv2.IMREAD_COLOR)
    if img is None:
        raise ValueError(f"Failed to decode image from: {image_path}")
    return img

def align_images_orb(im1: np.ndarray, im2: np.ndarray, max_features: int = 1000, match_ratio: float = 0.75) -> Tuple[np.ndarray, bool, str]:
    """
    Align im2 (comparison) to im1 (baseline) using ORB feature detection and Homography.
    Returns (aligned_image, alignment_success, alignment_warning).
    """
    gray1 = cv2.cvtColor(im1, cv2.COLOR_BGR2GRAY)
    gray2 = cv2.cvtColor(im2, cv2.COLOR_BGR2GRAY)

    orb = cv2.ORB_create(max_features)
    kp1, des1 = orb.detectAndCompute(gray1, None)
    kp2, des2 = orb.detectAndCompute(gray2, None)

    if des1 is None or des2 is None or len(kp1) < 4 or len(kp2) < 4:
        return im2, False, "Insufficient keypoints detected for feature-based alignment. Used standard dimension scaling."

    matcher = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=False)
    matches = matcher.knnMatch(des1, des2, k=2)

    good_matches = []
    for m, n in matches:
        if m.distance < match_ratio * n.distance:
            good_matches.append(m)

    if len(good_matches) < 8:
        return im2, False, f"Only {len(good_matches)} robust feature matches found; falling back to direct geometric resize."

    src_pts = np.float32([kp1[m.queryIdx].pt for m in good_matches]).reshape(-1, 1, 2)
    dst_pts = np.float32([kp2[m.trainIdx].pt for m in good_matches]).reshape(-1, 1, 2)

    homography, mask = cv2.findHomography(dst_pts, src_pts, cv2.RANSAC, 5.0)

    if homography is None:
        return im2, False, "Homography computation failed; falling back to direct scaling."

    # Validate homography transformation matrix to avoid extreme warping
    det = np.linalg.det(homography[0:2, 0:2])
    if det < 0.2 or det > 5.0:
        return im2, False, f"Alignment matrix determinant ({det:.2f}) indicates extreme distortion/viewpoint skew. Used direct scaling."

    height, width, _ = im1.shape
    aligned = cv2.warpPerspective(im2, homography, (width, height))
    return aligned, True, f"Successfully aligned images using {len(good_matches)} feature keypoint correspondences."

def compute_ssim_diff(im1_gray: np.ndarray, im2_gray: np.ndarray) -> Tuple[np.ndarray, float]:
    """
    Compute Structural Similarity (SSIM) difference map and mean score.
    SSIM is sensitive to structural changes, textures, and new construction rather than simple brightness shifts.
    """
    C1 = (0.01 * 255) ** 2
    C2 = (0.03 * 255) ** 2

    im1 = im1_gray.astype(np.float64)
    im2 = im2_gray.astype(np.float64)

    mu1 = cv2.GaussianBlur(im1, (11, 11), 1.5)
    mu2 = cv2.GaussianBlur(im2, (11, 11), 1.5)

    mu1_sq = mu1 ** 2
    mu2_sq = mu2 ** 2
    mu1_mu2 = mu1 * mu2

    sigma1_sq = cv2.GaussianBlur(im1 ** 2, (11, 11), 1.5) - mu1_sq
    sigma2_sq = cv2.GaussianBlur(im2 ** 2, (11, 11), 1.5) - mu2_sq
    sigma12 = cv2.GaussianBlur(im1 * im2, (11, 11), 1.5) - mu1_mu2

    ssim_map = ((2 * mu1_mu2 + C1) * (2 * sigma12 + C2)) / ((mu1_sq + mu2_sq + C1) * (sigma1_sq + sigma2_sq + C2))
    mean_ssim = float(np.mean(ssim_map))

    # Convert SSIM difference to visual error map (0-255)
    diff_map = ((1.0 - ssim_map) * 127.5).clip(0, 255).astype(np.uint8)
    return diff_map, mean_ssim

def run_image_comparison_pipeline(
    baseline_path: str,
    comparison_path: str,
    property_id: int
) -> Dict[str, Any]:
    """
    Full end-to-end Computer Vision analysis pipeline:
    1. Validation
    2. Dimension normalization
    3. Feature alignment (ORB)
    4. Differential SSIM & Absolute Difference
    5. Morphological filtering
    6. Heatmap generation
    7. Contours & Bounding Box extraction
    8. Change classification
    """
    # 1. Load images
    base_img = load_image_cv(baseline_path)
    comp_img = load_image_cv(comparison_path)

    # Standardize dimensions (standard 800x800 for high resolution inspection)
    target_size = (800, 800)
    base_resized = cv2.resize(base_img, target_size, interpolation=cv2.INTER_AREA)
    comp_resized = cv2.resize(comp_img, target_size, interpolation=cv2.INTER_AREA)

    # 2. Attempt feature alignment
    aligned_comp, alignment_ok, alignment_msg = align_images_orb(base_resized, comp_resized)

    # 3. Preprocessing
    base_gray = cv2.cvtColor(base_resized, cv2.COLOR_BGR2GRAY)
    comp_gray = cv2.cvtColor(aligned_comp, cv2.COLOR_BGR2GRAY)

    # Light histogram equalization / CLAHE to normalize differing solar illumination
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    base_eq = clahe.apply(base_gray)
    comp_eq = clahe.apply(comp_gray)

    # 4. Difference Computation
    # Combined Absolute difference + Structural Similarity
    abs_diff = cv2.absdiff(base_eq, comp_eq)
    ssim_diff, mean_ssim = compute_ssim_diff(base_eq, comp_eq)

    # Weighted composite difference map
    composite_diff = cv2.addWeighted(abs_diff, 0.4, ssim_diff, 0.6, 0)
    composite_blurred = cv2.GaussianBlur(composite_diff, (7, 7), 0)

    # Otsu thresholding to segment salient change areas
    _, thresh = cv2.threshold(composite_blurred, 45, 255, cv2.THRESH_BINARY)

    # Morphological opening/closing to eliminate isolated pixels & bridge solid alterations
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (7, 7))
    cleaned_mask = cv2.morphologyEx(thresh, cv2.MORPH_OPEN, kernel)
    cleaned_mask = cv2.morphologyEx(cleaned_mask, cv2.MORPH_CLOSE, kernel)

    # 5. Extract Contours & Bounding Boxes
    contours, _ = cv2.findContours(cleaned_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    
    total_area = target_size[0] * target_size[1]
    significant_contours = []
    changed_area = 0

    # Annotated image overlay
    annotated = aligned_comp.copy()

    for cnt in contours:
        area = cv2.contourArea(cnt)
        if area > 450: # filter out minor sensor noise
            significant_contours.append(cnt)
            changed_area += area
            x, y, w, h = cv2.boundingRect(cnt)
            # Draw glowing bounding box
            cv2.rectangle(annotated, (x, y), (x + w, y + h), (0, 69, 255), 2) # Crimson Orange
            cv2.putText(
                annotated,
                f"Mod: {int(area)}px",
                (x, max(20, y - 6)),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.5,
                (0, 69, 255),
                1,
                cv2.LINE_AA
            )

    changed_percentage = min(100.0, round((changed_area / total_area) * 100.0, 2))
    # Normalized change score (scaling SSIM loss and pixel ratio)
    structural_loss = (1.0 - mean_ssim) * 100.0
    change_score = round(min(100.0, max(0.0, (changed_percentage * 1.8) + (structural_loss * 0.4))), 1)

    # Classification
    if change_score < 8.0:
        classification = "Low"
        explanation = (
            f"Minimal visual deviation detected (score: {change_score}%). "
            f"Identified {len(significant_contours)} minor localized variance cluster(s). "
            f"Likely attributable to natural seasonal vegetation variation, lighting differences, or atmospheric sensor noise."
        )
    elif change_score < 25.0:
        classification = "Moderate"
        explanation = (
            f"Moderate physical alteration detected (score: {change_score}%). "
            f"Detected {len(significant_contours)} significant region(s) representing {changed_percentage}% of the property envelope. "
            f"Possible new rooftop structure, solar panel array, ground excavation, or patio extension."
        )
    else:
        classification = "High"
        explanation = (
            f"Substantial structural change detected (score: {change_score}%). "
            f"Found {len(significant_contours)} prominent altered sector(s) encompassing {changed_percentage}% of property surface. "
            f"High confidence signal for building footprint extension, new auxiliary building, or major structural addition."
        )

    # 6. Generate Heatmap
    # Normalize composite diff to 0-255 for colormap
    norm_diff = cv2.normalize(composite_blurred, None, 0, 255, cv2.NORM_MINMAX)
    heatmap_colored = cv2.applyColorMap(norm_diff, cv2.COLORMAP_JET)
    
    # Blend heatmap over the comparison image with 55% transparency
    heatmap_blend = cv2.addWeighted(aligned_comp, 0.45, heatmap_colored, 0.55, 0)

    # 7. Save Artifacts to Storage
    analysis_uid = uuid.uuid4().hex[:10]
    diff_filename = f"diff_{property_id}_{analysis_uid}.png"
    heatmap_filename = f"heatmap_{property_id}_{analysis_uid}.png"

    diff_dest = settings.HEATMAPS_DIR / diff_filename
    heatmap_dest = settings.HEATMAPS_DIR / heatmap_filename

    # Save images using cv2
    cv2.imwrite(str(diff_dest), annotated)
    cv2.imwrite(str(heatmap_dest), heatmap_blend)

    limitations = (
        "Computer vision change signals indicate visual variance between images. "
        "False positives can be caused by differing camera angles, cloud shadows, seasonal vegetation, "
        "or sun azimuth differences. Findings constitute preliminary signals and require human review."
    )

    return {
        "algorithm_name": "OpenCV ORB Alignment + CLAHE + Differential SSIM + Contour Analysis",
        "change_score": change_score,
        "changed_area_percentage": changed_percentage,
        "diff_image_path": f"/static/heatmaps/{diff_filename}",
        "heatmap_image_path": f"/static/heatmaps/{heatmap_filename}",
        "contours_count": len(significant_contours),
        "analysis_result": classification,
        "explanation": explanation,
        "limitations": limitations,
        "alignment_status": alignment_msg,
        "mean_ssim": round(mean_ssim, 4)
    }
