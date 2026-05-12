from core.renderer import Renderer
from rendercanvas.auto import loop

WIDTH, HEIGHT = 800, 600


def main():
    # Inicializácia WGPU Rendereru (ktorý už interné rieši plátno aj vykresľovanie)
    renderer = Renderer(title="VoidSeek", width=WIDTH, height=HEIGHT)

    print("Okno úspešne vytvorené s wgpu. Pre ukončenie ho zavrite/stlačte ESC.")

    # Spustenie hlavnej synchrónnej slučky pre rendercanvas / glfw okno
    loop.run()


if __name__ == "__main__":
    main()