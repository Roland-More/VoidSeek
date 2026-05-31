import sys
import ctypes

try:
    # Upozorníme Windows, že sme DPI aware, aby nám plátno neorezával/neškáloval
    ctypes.windll.user32.SetProcessDPIAware()
except Exception:
    pass

import wgpu
from core.renderer import Renderer
from rendercanvas.auto import loop

# Získanie rozlíšenia obrazovky (pre Windows) a zmenšenie na štvrtinu
user32 = ctypes.windll.user32
WIDTH, HEIGHT = user32.GetSystemMetrics(0) // 4, user32.GetSystemMetrics(1) // 4


def main():
    # Inicializácia WGPU Rendereru (ktorý už interné rieši plátno aj vykresľovanie)
    renderer = Renderer(title="VoidSeek", width=WIDTH, height=HEIGHT)

    print("Okno úspešne vytvorené s wgpu. Pre ukončenie ho zavrite/stlačte ESC.")

    # Spustenie hlavnej synchrónnej slučky pre rendercanvas / glfw okno
    loop.run()


if __name__ == "__main__":
    main()