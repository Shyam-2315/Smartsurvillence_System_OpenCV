import cv2
import numpy as np

def enhance(image: np.ndarray, options: dict) -> np.ndarray:
    result = image.copy()
    if options.get("deskew"):
        gray = cv2.cvtColor(result, cv2.COLOR_BGR2GRAY)
        points = np.column_stack(np.where(gray < 200))
        if len(points) > 20:
            angle = cv2.minAreaRect(points[:, ::-1].astype(np.float32))[-1]
            angle = -(90 + angle) if angle < -45 else -angle
            if abs(angle) <= 15:
                h, w = result.shape[:2]
                matrix = cv2.getRotationMatrix2D((w / 2, h / 2), angle, 1)
                result = cv2.warpAffine(result, matrix, (w, h), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE)
    if options.get("auto_contrast"):
        result = cv2.normalize(result, None, 0, 255, cv2.NORM_MINMAX)
    if options.get("clahe"):
        lab = cv2.cvtColor(result, cv2.COLOR_BGR2LAB); l, a, b = cv2.split(lab)
        result = cv2.cvtColor(cv2.merge((cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8,8)).apply(l), a, b)), cv2.COLOR_LAB2BGR)
    if options.get("denoise"):
        result = cv2.fastNlMeansDenoisingColored(result, None, 5, 5, 7, 21)
    result = cv2.convertScaleAbs(result, alpha=float(options.get("contrast", 1)), beta=int(options.get("brightness", 0)))
    gamma = float(options.get("gamma", 1))
    if gamma != 1:
        table = np.array([((i / 255.0) ** (1 / gamma)) * 255 for i in range(256)]).astype("uint8")
        result = cv2.LUT(result, table)
    amount = float(options.get("sharpen", 0))
    if amount:
        blurred = cv2.GaussianBlur(result, (0, 0), 2)
        result = cv2.addWeighted(result, 1 + amount, blurred, -amount, 0)
    if options.get("grayscale"):
        result = cv2.cvtColor(result, cv2.COLOR_BGR2GRAY)
    scale = int(options.get("upscale", 1))
    if scale > 1:
        result = cv2.resize(result, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)
    return result
