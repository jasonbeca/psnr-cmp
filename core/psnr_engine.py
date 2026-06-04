"""
PSNR Calculation Engine
Block-based PSNR calculation for Y, U, V components.
"""
import numpy as np


def calculate_psnr(ref: np.ndarray, tgt: np.ndarray, max_val: int = 255) -> float:
    """
    Calculate PSNR between two arrays.
    
    Args:
        ref: Reference array
        tgt: Target array
        max_val: Maximum pixel value (255 for 8-bit)
        
    Returns:
        PSNR value in dB (float('inf') if identical)
    """
    mse = np.mean((ref.astype(np.float64) - tgt.astype(np.float64)) ** 2)
    if mse == 0:
        return float('inf')
    return 10 * np.log10((max_val ** 2) / mse)


def calculate_block_psnr(
    ref_plane: np.ndarray,
    tgt_plane: np.ndarray,
    block_size: int,
    max_val: int = 255
) -> np.ndarray:
    """
    Calculate PSNR for each block in the image.
    
    Args:
        ref_plane: Reference image plane (Y, U, or V)
        tgt_plane: Target image plane
        block_size: Block size in pixels
        max_val: Maximum pixel value
        
    Returns:
        2D numpy array of PSNR values for each block
    """
    height, width = ref_plane.shape
    blocks_y = (height + block_size - 1) // block_size
    blocks_x = (width + block_size - 1) // block_size
    
    psnr_grid = np.zeros((blocks_y, blocks_x), dtype=np.float64)
    
    for by in range(blocks_y):
        for bx in range(blocks_x):
            y_start = by * block_size
            y_end = min(y_start + block_size, height)
            x_start = bx * block_size
            x_end = min(x_start + block_size, width)
            
            ref_block = ref_plane[y_start:y_end, x_start:x_end]
            tgt_block = tgt_plane[y_start:y_end, x_start:x_end]
            
            psnr_grid[by, bx] = calculate_psnr(ref_block, tgt_block, max_val)
    
    return psnr_grid


def calculate_combined_psnr(
    ref_y: np.ndarray, ref_u: np.ndarray, ref_v: np.ndarray,
    tgt_y: np.ndarray, tgt_u: np.ndarray, tgt_v: np.ndarray,
    block_size: int,
    components: str = "yuv"
) -> np.ndarray:
    """
    Calculate combined PSNR based on selected components.
    
    Args:
        ref_y, ref_u, ref_v: Reference YUV planes
        tgt_y, tgt_u, tgt_v: Target YUV planes
        block_size: Block size for Y plane
        components: String containing 'y', 'u', 'v' for selected components
        
    Returns:
        2D numpy array of combined PSNR values
    """
    components = components.lower()
    psnr_sum = None
    count = 0
    
    if 'y' in components:
        psnr_y = calculate_block_psnr(ref_y, tgt_y, block_size)
        psnr_sum = psnr_y if psnr_sum is None else psnr_sum + psnr_y
        count += 1
    
    if 'u' in components:
        # UV planes may be smaller, use proportional block size
        uv_block_size = block_size // 2 if ref_u.shape[0] < ref_y.shape[0] else block_size
        psnr_u = calculate_block_psnr(ref_u, tgt_u, max(1, uv_block_size))
        # Upsample to match Y grid size if needed
        if psnr_u.shape != psnr_sum.shape if psnr_sum is not None else False:
            psnr_u = np.repeat(np.repeat(psnr_u, 2, axis=0), 2, axis=1)
            psnr_u = psnr_u[:psnr_sum.shape[0], :psnr_sum.shape[1]]
        if psnr_sum is None:
            psnr_sum = psnr_u
        else:
            psnr_sum = psnr_sum + psnr_u
        count += 1
    
    if 'v' in components:
        uv_block_size = block_size // 2 if ref_v.shape[0] < ref_y.shape[0] else block_size
        psnr_v = calculate_block_psnr(ref_v, tgt_v, max(1, uv_block_size))
        if psnr_v.shape != psnr_sum.shape if psnr_sum is not None else False:
            psnr_v = np.repeat(np.repeat(psnr_v, 2, axis=0), 2, axis=1)
            psnr_v = psnr_v[:psnr_sum.shape[0], :psnr_sum.shape[1]]
        if psnr_sum is None:
            psnr_sum = psnr_v
        else:
            psnr_sum = psnr_sum + psnr_v
        count += 1
    
    if count == 0:
        raise ValueError("No components selected")
    
    return psnr_sum / count
