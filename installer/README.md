# Instalador nativo para Windows

`Desembarque.iss` é um script do [Inno Setup](https://jrsoftware.org/isinfo.php)
(gratuito, 6.2 ou mais novo) que gera `Output\Desembarque-Setup.exe`:

- copia o programa para `%LOCALAPPDATA%\Desembarque` (por usuário, sem
  administrador);
- se não há Python, baixa o 3.12 de python.org e o instala em silêncio, por
  usuário, **sem mexer no PATH** — o passo que o teste de 2026-10-17 mostrou
  que uma pessoa sem terminal não faz;
- cria "Desembarque" no menu Iniciar e na Área de trabalho; a primeira
  abertura é a janela de sempre, que instala os leitores (uns 3 GB) em
  `.venv-ocr` pelo mesmo caminho do ZIP (`launcher/core.py`);
- o desinstalador (Adicionar ou remover programas) apaga o programa,
  `.venv-ocr` e, se a pessoa quiser, o modelo em `%USERPROFILE%\.cache\kraken`;
  os PDFs e as subpastas `transcriptions` ficam.

## Gerar o instalador (no Windows)

1. Instale o Inno Setup.
2. Abra `installer\Desembarque.iss` no Inno Setup Compiler e pressione
   **Build** (Ctrl+F9) — ou, no prompt, na raiz do repositório:
   `"%ProgramFiles(x86)%\Inno Setup 6\iscc.exe" installer\Desembarque.iss`.
3. O resultado fica em `installer\Output\Desembarque-Setup.exe` (uns 2 MB:
   os leitores não vão dentro, são baixados na primeira abertura).

## Ainda não testado

Escrito no Linux, que não roda o Inno Setup. Checklist da primeira vez:

- [ ] compila sem erro;
- [ ] numa máquina sem Python: baixa, instala, abre a janela;
- [ ] numa máquina com Python da python.org: não baixa de novo;
- [ ] a janela encontra a placa NVIDIA e oferece os leitores de GPU;
- [ ] desinstalar apaga `.venv-ocr` e pergunta pelo modelo;
- [ ] uma cópia antiga do ZIP com `.venv-ocr` (Desktop, Downloads) — o
  instalador não a vê: apague-a à mão, ou use a janela antiga → Verificar a
  instalação → Desinstalar antes. (Detectar e migrar a venv antiga está no
  relatório §2 como pedido; não feito.)
