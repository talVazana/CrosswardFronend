import os
import cv2
import numpy as np
import json
from scipy.signal import find_peaks

def auto_threshold_dark(grid_crop, n_rows, n_cols):
    """Compute adaptive bimodal intensity threshold separating black/shaded from white cells."""
    sample_means = []
    ch = grid_crop.shape[0] / float(n_rows)
    cw = grid_crop.shape[1] / float(n_cols)
    for r in range(n_rows):
        for c in range(n_cols):
            y1 = int((r + 0.25) * ch)
            y2 = int((r + 0.75) * ch)
            x1 = int((c + 0.25) * cw)
            x2 = int((c + 0.75) * cw)
            sample_means.append(np.mean(grid_crop[y1:y2, x1:x2]))
    
    sample_means = np.array(sample_means)
    c1, c2 = np.min(sample_means), np.max(sample_means)
    for _ in range(10):
        group1 = sample_means[np.abs(sample_means - c1) <= np.abs(sample_means - c2)]
        group2 = sample_means[np.abs(sample_means - c1) > np.abs(sample_means - c2)]
        if len(group1) > 0: c1 = np.mean(group1)
        if len(group2) > 0: c2 = np.mean(group2)
    return (c1 + c2) / 2.0

def get_grid_roi(gray):
    """Accurately localize the crossword grid region of interest."""
    thresh = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY_INV, 15, 5)
    k_size = max(25, int(gray.shape[1] * 0.04))
    lh = cv2.morphologyEx(thresh, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_RECT, (k_size, 1)))
    lv = cv2.morphologyEx(thresh, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_RECT, (1, k_size)))
    
    mask = (lh | lv)[:, :int(gray.shape[1] * 0.72)]
    cnts, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    large_cnts = [c for c in cnts if cv2.boundingRect(c)[2] > 350 and cv2.boundingRect(c)[3] > 350]
    
    if large_cnts:
        best = max(large_cnts, key=lambda c: cv2.boundingRect(c)[2] * cv2.boundingRect(c)[3])
        x, y, w, h = cv2.boundingRect(best)
        return gray[y:y+h, x:x+w], (x, y, w, h)
        
    edges = cv2.Canny(gray, 50, 150)
    cnts, _ = cv2.findContours(edges, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
    for c in sorted(cnts, key=cv2.contourArea, reverse=True):
        x, y, w, h = cv2.boundingRect(c)
        if 0.75 < w/float(h) < 1.35 and w > 350 and h > 350 and x < int(gray.shape[1] * 0.35):
            return gray[y:y+h, x:x+w], (x, y, w, h)
    return gray, (0, 0, gray.shape[1], gray.shape[0])

WORKING_GRID_SIZE = 1100


def _resize_for_analysis(image, target=WORKING_GRID_SIZE):
    height, width = image.shape[:2]
    longest = max(height, width)
    if longest <= 0 or longest == target:
        return image
    scale = target / float(longest)
    new_width = max(1, int(round(width * scale)))
    new_height = max(1, int(round(height * scale)))
    interpolation = cv2.INTER_AREA if scale < 1 else cv2.INTER_CUBIC
    return cv2.resize(
        image,
        (new_width, new_height),
        interpolation=interpolation,
    )


def _axis_boundaries(profile, cells):
    length = len(profile)
    if length == 0:
        return np.array([], dtype=int)
    distance = max(1, int(length / float(cells) * 0.7))
    peaks, _ = find_peaks(-profile, distance=distance, prominence=3)
    peaks = np.asarray(peaks, dtype=int)
    margin = max(40, int(length * 0.04))

    if peaks.size == 0:
        return np.linspace(0, length - 1, cells + 1).astype(int)

    if peaks[0] > margin:
        peaks = np.insert(peaks, 0, int(np.argmin(profile[:margin])))
    if peaks[-1] < length - margin:
        tail = profile[-margin:][::-1]
        peaks = np.append(peaks, length - 1 - int(np.argmin(tail)))

    if len(peaks) != cells + 1:
        return np.linspace(0, length - 1, cells + 1).astype(int)
    return peaks


def parse_crossword_image(image_path):
    img = cv2.imread(image_path)
    if img is None:
        raise FileNotFoundError(f"Cannot load image: {image_path}")
    gray = _resize_for_analysis(cv2.cvtColor(img, cv2.COLOR_BGR2GRAY))

    grid_crop, (_gx, _gy, _gw, _gh) = get_grid_roi(gray)
    grid_h, grid_w = grid_crop.shape[:2]

    h_prof = np.mean(grid_crop, axis=1)
    v_prof = np.mean(grid_crop, axis=0)

    p13_h, _ = find_peaks(-h_prof, distance=max(1, int(grid_h / 13.0 * 0.7)), prominence=3)
    p13_v, _ = find_peaks(-v_prof, distance=max(1, int(grid_w / 13.0 * 0.7)), prominence=3)

    if len(p13_h) >= 13 and len(p13_v) >= 13:
        nr, nc = 13, 13
    else:
        nr, nc = 11, 11

    peaks_h = _axis_boundaries(h_prof, nr)
    peaks_v = _axis_boundaries(v_prof, nc)

    dark_thresh = auto_threshold_dark(grid_crop, nr, nc)

    mat = []
    for r in range(nr):
        row = []
        for c in range(nc):
            y1, y2 = peaks_h[r], peaks_h[r + 1]
            x1, x2 = peaks_v[c], peaks_v[c + 1]

            m_y = max(3, int((y2 - y1) * 0.08))
            m_x = max(3, int((x2 - x1) * 0.08))
            cell = grid_crop[y1 + m_y : y2 - m_y, x1 + m_x : x2 - m_x]

            row.append(0 if np.mean(cell) < dark_thresh else 1)
        mat.append(row)

    return mat, nr, nc


def generate_crossword_json(mat, nr, nc):
    """Process matrix with right-to-left, top-to-bottom scanning for sequential numbering."""
    clues = []
    numbered_matrix = [
        [0 if mat[r][c] == 0 else 1 for c in range(nc)]
        for r in range(nr)
    ]
    clue_counter = 1

    # Iterate row by row (top to bottom), but column by column from right (nc - 1) to left (0)
    for r in range(nr):
        for c in range(nc - 1, -1, -1):
            if mat[r][c] == 0:
                continue

            current_clue_number = clue_counter

            is_horizontal = False
            is_vertical = False

            # Hebrew horizontal logic: Word goes Right-to-Left
            right_is_blocked = (c == nc - 1) or (mat[r][c + 1] == 0)
            left_is_open = (c > 0) and (mat[r][c - 1] != 0)
            if right_is_blocked and left_is_open:
                is_horizontal = True

            # Vertical logic: Word goes Top-to-Bottom
            top_is_blocked = (r == 0) or (mat[r - 1][c] == 0)
            bottom_is_open = (r < nr - 1) and (mat[r + 1][c] != 0)
            if top_is_blocked and bottom_is_open:
                is_vertical = True

            if not (is_horizontal or is_vertical):
                continue

            numbered_matrix[r][c] = 2
            clues.append({
                "clue_number": current_clue_number,
                "row": r,
                "col": c,
                "horizontal": is_horizontal,
                "vertical": is_vertical
            })
            clue_counter += 1

    return {
        "rows": nr,
        "cols": nc,
        "matrix": numbered_matrix,
        "clues": clues
    }

if __name__ == "__main__":
    # Execute parsing and save as JSON
    for img_name in ['a.jpg']:
        if os.path.exists(img_name):
            detected_mat, nr, nc = parse_crossword_image(img_name)

            json_data = generate_crossword_json(detected_mat, nr, nc)

            json_filename = img_name.replace('.jpg', '_output.json')
            with open(json_filename, 'w', encoding='utf-8') as json_file:
                json.dump(json_data, json_file, indent=4, ensure_ascii=False)

            print(f"Matrix and right-to-left sequential numbering successful. Output saved to: {json_filename}")