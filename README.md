# VoidSeek

VoidSeek je grafický a herný projekt v Pythone, ktorý demonštruje využitie moderného grafického API **WebGPU** (komunikujúci cez knižnicu `wgpu-py` a `GLFW`).

Projekt implementuje vlastný engine postavený na moderných architektonických princípoch:

- **Hardvérovo akcelerovaný rendering:** Vysoko výkonný backend postavený na WGPU, ktorý natívne pristupuje k GPU.
- **Compute Shaders (WGSL):** Využitie výpočtových shaderov pre pokročilý raycasting a vizuálne retro efekty.
- **Architektúra ECS (Entity-Component-System):** Moderný, čistý a škálovateľný prístup k správe hernej logiky, entít a herného stavu.
- **Vlastná abstrakcia grafickej pipeline:** Modulárna správa textúr, atlasov, bind group layoutov a compute pipeline.

## Lokálna inštalácia knižníc (Odporúčané)

Aby sme nezašpinili globálny Python v počítači a vyhli sa problémom s verziami, tento projekt by mal používať **virtuálne prostredie (venv)**. Vďaka tomu sa všetky knižnice stiahnu priamo do tohto priečinka a neovplyvnia iné projekty.

### 1. Vytvorenie virtuálneho prostredia (venv)

Pokiaľ ešte nemáte vytvorené prostredie, vytvorte ho týmto príkazom. Vytvorí sa v priečinku `.venv` (ktorý je ignorovaný v gite):

```powershell
python -m venv .venv
```

### 2. Aktivácia virtuálneho prostredia

Pred inštaláciou alebo spúšťaním projektu **musíte** prostredie aktivovať:

**Na systéme Windows (PowerShell):**

```powershell
.venv\Scripts\activate
```

_(Ak by PowerShell vypísal chybu o vykonávaní skriptov, použite `Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser`)_

**Na systéme Linux/macOS:**

```bash
source .venv/bin/activate
```

Po úspešnej aktivácii uvidíte v termináli na začiatku riadku napis `(.venv)`.

### 3. Inštalácia závislostí

Keď je venv aktívny, stiahnu sa v knižnice konkrétnych verzií (`glfw` a `wgpu`) priamo doňho príkazom:

```powershell
pip install -r requirements.txt
```

---

## Spustenie

Uistite sa, že máte aktivované virtuálne prostredie `(.venv)` a spustite aplikáciu:

```powershell
python src/main.py
```

---

## Ako hrať VoidSeek

**VoidSeek** je asymetrická multiplayerová hra (1 vs X), v ktorej sa hráči delia na dve role: **Seeker (Hľadač)** a **Runner (Bežec)**.

### Cieľ hry

- **🏃‍♂️ Runneri:** Vašou úlohou je utiecť z mapy. Aby ste to dokázali, musíte:
  1. Nájsť a zobrať **kľúč (Key)**.
  2. S kľúčom nájsť **portál (Portal)** a odomknúť ho.
  3. Prejsť otvoreným portálom a uniknúť (Escape).
  4. Ak ste v úzkych, môžete sa skrývať a využívať **ventilačné šachty (Vents)** na rýchly presun po mape. Vyhýbajte sa Seekerovi za každú cenu!

- **👁️ Seeker:** Vašou úlohou je eliminovať všetkých Runnerov predtým, než stihnú uniknúť.
  1. Ste o niečo rýchlejší ako Runneri.
  2. Kliknutím **Ľavým tlačidlom myši (LMB)** zaútočíte na Runnera, ktorý je vo vašej blízkosti.

### Mechaniky a Ovládanie

- **Pohyb:** `W`, `A`, `S`, `D`
- **Kamera:** Pohybom myši
- **Útok (Iba Seeker):** `Ľavé tlačidlo myši`
- **Interakcia s ventilačkou (Iba Runner):** Príďte k ventilačke a vstúpte do nej.
