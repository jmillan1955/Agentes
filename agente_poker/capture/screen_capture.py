import os
from datetime import datetime
from pathlib import Path

import mss
import mss.tools
from dotenv import load_dotenv


class ScreenCapture:

    def __init__(self):
        load_dotenv()

        self.left = int(
            os.getenv(
                "CAPTURE_LEFT",
                "0",
            )
        )

        self.top = int(
            os.getenv(
                "CAPTURE_TOP",
                "0",
            )
        )

        self.width = int(
            os.getenv(
                "CAPTURE_WIDTH",
                "800",
            )
        )

        self.height = int(
            os.getenv(
                "CAPTURE_HEIGHT",
                "600",
            )
        )
        project_root = Path(__file__).resolve().parents[1]

        self.output_dir = (
            project_root / "captures"
        )

        self.output_dir.mkdir(
            parents=True,
            exist_ok=True,
        )

    def capture(self) -> Path:
        """
        Captura la región configurada en .env
        y devuelve la ruta del PNG generado.
        """

        timestamp = datetime.now().strftime(
            "%Y%m%d_%H%M%S_%f"
        )

        output_path = (
            self.output_dir
            / f"capture_{timestamp}.png"
        )

        monitor = {
            "left": self.left,
            "top": self.top,
            "width": self.width,
            "height": self.height,
        }

        with mss.mss() as sct:

            screenshot = sct.grab(
                monitor
            )

            mss.tools.to_png(
                screenshot.rgb,
                screenshot.size,
                output=str(output_path),
            )

        return output_path

if __name__ == "__main__":

    capture = ScreenCapture()

    path = capture.capture()

    print(
        f"Captura guardada en: {path}"
    )