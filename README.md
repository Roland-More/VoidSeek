# VoidSeek

C++ / Python grafický projekt využívajúci GLFW a WGPU.

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

*(Ak by PowerShell vypísal chybu o vykonávaní skriptov, použite `Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser`)*

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
python main.py
```
