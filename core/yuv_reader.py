"""
YUV Reader Module
Handles reading raw YUV files and decoding video streams via ffmpeg.
"""
import subprocess
import numpy as np
from pathlib import Path


class YUVReader:
    """Reads raw YUV files and decodes video streams."""

    def __init__(self, width: int, height: int, yuv_format: str = "420"):
        """
        Initialize YUV reader.
        
        Args:
            width: Frame width in pixels
            height: Frame height in pixels
            yuv_format: YUV format - "420", "422", or "444"
        """
        self.width = width
        self.height = height
        self.yuv_format = yuv_format
        self._frame_size = self._calculate_frame_size()
        self._ffmpeg_checked = False
        self._ffmpeg_available = False

    def _check_ffmpeg(self):
        """Check if ffmpeg is available."""
        if self._ffmpeg_checked:
            return self._ffmpeg_available
            
        try:
            # Check PATH first
            subprocess.run(['ffmpeg', '-version'], capture_output=True, check=True)
            self._ffmpeg_available = True
        except (subprocess.CalledProcessError, FileNotFoundError):
            # Check local directory (for packaged builds)
            local_ffmpeg = Path("ffmpeg.exe").absolute()
            if local_ffmpeg.exists():
                self._ffmpeg_available = True
            else:
                self._ffmpeg_available = False
        
        self._ffmpeg_checked = True
        return self._ffmpeg_available

    def _calculate_frame_size(self) -> int:
        """Calculate frame size in bytes based on YUV format."""
        y_size = self.width * self.height
        if self.yuv_format == "420":
            uv_size = (self.width // 2) * (self.height // 2) * 2
        elif self.yuv_format == "422":
            uv_size = (self.width // 2) * self.height * 2
        elif self.yuv_format == "444":
            uv_size = self.width * self.height * 2
        else:
            raise ValueError(f"Unsupported YUV format: {self.yuv_format}")
        return y_size + uv_size

    def get_frame_count(self, file_path: str) -> int:
        """Get total number of frames in a raw YUV file."""
        file_size = Path(file_path).stat().st_size
        return file_size // self._frame_size

    def read_yuv_frame(self, file_path: str, frame_idx: int) -> tuple:
        """
        Read a single frame from a raw YUV file.
        
        Args:
            file_path: Path to raw YUV file
            frame_idx: Frame index (0-based)
            
        Returns:
            Tuple of (Y, U, V) numpy arrays
        """
        with open(file_path, 'rb') as f:
            f.seek(frame_idx * self._frame_size)
            frame_data = f.read(self._frame_size)

        if len(frame_data) < self._frame_size:
            raise ValueError(f"Could not read frame {frame_idx}")

        return self._parse_yuv_data(frame_data)

    def _parse_yuv_data(self, data: bytes) -> tuple:
        """Parse raw YUV bytes into Y, U, V planes."""
        y_size = self.width * self.height
        y_plane = np.frombuffer(data[:y_size], dtype=np.uint8).reshape(self.height, self.width)

        if self.yuv_format == "420":
            uv_width = self.width // 2
            uv_height = self.height // 2
        elif self.yuv_format == "422":
            uv_width = self.width // 2
            uv_height = self.height
        else:  # 444
            uv_width = self.width
            uv_height = self.height

        uv_size = uv_width * uv_height
        u_plane = np.frombuffer(data[y_size:y_size + uv_size], dtype=np.uint8).reshape(uv_height, uv_width)
        v_plane = np.frombuffer(data[y_size + uv_size:y_size + 2 * uv_size], dtype=np.uint8).reshape(uv_height, uv_width)

        return y_plane, u_plane, v_plane

    def decode_stream_frame(self, stream_path: str, frame_idx: int) -> tuple:
        """
        Decode a frame from a video stream using ffmpeg.
        
        Args:
            stream_path: Path to video file (h264, hevc, etc.)
            frame_idx: Frame index (0-based)
            
        Returns:
            Tuple of (Y, U, V) numpy arrays
        """
        if not self._check_ffmpeg():
             raise RuntimeError("FFmpeg not found! Please install FFmpeg to read video streams.")

        # Calculate bytes needed for one frame
        y_size = self.width * self.height
        if self.yuv_format == "420":
            pix_fmt = "yuv420p"
            uv_size = (self.width // 2) * (self.height // 2) * 2
        elif self.yuv_format == "422":
            pix_fmt = "yuv422p"
            uv_size = (self.width // 2) * self.height * 2
        else:
            pix_fmt = "yuv444p"
            uv_size = self.width * self.height * 2

        total_size = y_size + uv_size

        # Use local ffmpeg if in current directory (for packaged builds)
        ffmpeg_cmd = 'ffmpeg'
        if Path("ffmpeg.exe").exists():
            ffmpeg_cmd = str(Path("ffmpeg.exe").absolute())

        cmd = [
            ffmpeg_cmd,
            '-i', stream_path,
            '-vf', f'select=eq(n\\,{frame_idx})',
            '-vframes', '1',
            '-s', f'{self.width}x{self.height}',
            '-pix_fmt', pix_fmt,
            '-f', 'rawvideo',
            '-'
        ]

        try:
            # Hide console window on Windows
            startupinfo = None
            if hasattr(subprocess, 'STARTUPINFO'):
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW

            result = subprocess.run(cmd, capture_output=True, check=True, startupinfo=startupinfo)
            data = result.stdout
            if len(data) < total_size:
                raise ValueError(f"FFmpeg output too short: {len(data)} < {total_size}")
            return self._parse_yuv_data(data)
        except subprocess.CalledProcessError as e:
            raise RuntimeError(f"FFmpeg failed: {e.stderr.decode()}")

    def get_stream_frame_count(self, stream_path: str) -> int:
        """Get total frame count from a video stream using ffprobe."""
        if not self._check_ffmpeg():
            return 0

        # Use local ffprobe if available
        ffprobe_cmd = 'ffprobe'
        if Path("ffprobe.exe").exists():
            ffprobe_cmd = str(Path("ffprobe.exe").absolute())

        cmd = [
            ffprobe_cmd,
            '-v', 'error',
            '-select_streams', 'v:0',
            '-count_packets',
            '-show_entries', 'stream=nb_read_packets',
            '-of', 'csv=p=0',
            stream_path
        ]
        try:
            # Hide console window on Windows
            startupinfo = None
            if hasattr(subprocess, 'STARTUPINFO'):
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW

            result = subprocess.run(cmd, capture_output=True, check=True, text=True, startupinfo=startupinfo)
            return int(result.stdout.strip())
        except (subprocess.CalledProcessError, ValueError):
            return 0
