import glfw
import sys

WIDTH, HEIGHT = 800, 600

def main():
    # Inicializácia GLFW
    if not glfw.init():
        print("Nepodarilo sa inicializovať GLFW")
        sys.exit(1)

    # Dôležité pre WGPU/Vulkan - hovoríme GLFW, aby nevytváralo OpenGL kontext
    glfw.window_hint(glfw.CLIENT_API, glfw.NO_API)
    glfw.window_hint(glfw.RESIZABLE, glfw.TRUE)

    # Vytvorenie okna (Šírka, Výška, Názov, Monitor, Zdieľanie)
    window = glfw.create_window(WIDTH, HEIGHT, "VoidSeek", None, None)
    if not window:
        glfw.terminate()
        print("Nepodarilo sa vytvoriť GLFW okno")
        sys.exit(1)

    print("Okno úspešne vytvorené. Pre ukončenie ho zavrite.")

    # Hlavná slučka okna
    while not glfw.window_should_close(window):
        # Tu sa neskôr pridá renderovanie cez WGPU
        
        # Spracovanie udalostí okna (klávesnica, myš, zavretie)
        glfw.poll_events()

    # Vyčistenie
    glfw.terminate()

if __name__ == "__main__":
    main()
