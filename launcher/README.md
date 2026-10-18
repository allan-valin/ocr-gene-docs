# Desembarque — como usar sem terminal

1. **Instale o Python** (uma vez) — veja o seu sistema abaixo.
2. **Baixe esta pasta** (botão verde *Code → Download ZIP* na página do
   projeto) e descompacte onde quiser. Cada sistema precisa da sua própria
   cópia: a pasta instalada no Linux não serve no Windows, nem ao contrário.
3. **Abra o arquivo do seu sistema** com um clique duplo — veja abaixo.
4. A janela que abre confere o que está instalado, em três partes: **Leitura**
   (abrir, ver e buscar o que já foi transcrito), **Motor de transcrição** e
   **Leitor de letra manuscrita**. Se faltar alguma, uma janela diz qual e
   oferece **Instalar o que falta** (leva alguns minutos, precisa de internet,
   cerca de 3 GB ao todo) ou **Continuar assim** — só a Leitura basta para
   usar PDFs já transcritos, de um pendrive por exemplo; sem o leitor de
   manuscritos os nomes à mão saem na leitura fraca do motor.
5. Em **Pasta com os PDFs**, escolha a pasta onde estão as listas de passageiros.
6. **Ligar**. Inicia o programa que lê os PDFs, o navegador abre sozinho na
   página do Desembarque, que mostra "aquecendo o leitor…" enquanto os
   modelos carregam (1 a 2 minutos; desligue **Aquecer os leitores ao
   ligar** para uma sessão só de busca). A janela diz em que documento está,
   quantos faltam e quanto tempo; **Ler usando** mostra o tempo por página
   medido nesta máquina.
   Na página, a faixa de baixo ("O que está acontecendo") diz o que cada
   clique fez e o que o programa está fazendo agora.
7. Quando terminar, **Desligar** — ou feche a janela, ou a aba do navegador:
   qualquer um dos três desliga. O que já foi lido fica salvo na subpasta
   `transcriptions`, dentro da pasta dos PDFs; da próxima vez continua de
   onde parou.

**Ajuda (F1)** na janela explica cada botão, o que faz e por quê.

Tudo roda no seu computador. Nada é enviado para fora dele.

## Por sistema

### Windows

- Abra **`Desembarque.bat`** com dois cliques. Ele procura um Python 3
  instalado (o da python.org, em qualquer pasta, com ou sem PATH; o `py`);
  se não há nenhum, baixa o Python 3.12 da python.org e o instala sozinho,
  por usuário, sem mexer no PATH (uns 25 MB, 1 a 2 minutos; uma janela
  preta mostra o andamento). Não é preciso instalar o Python antes.
- Se preferir instalar o Python à mão: https://www.python.org/downloads/
  (3.12), com as opções que vierem; marcar "Add python.exe to PATH" não é
  mais necessário.
- A pasta dos PDFs tem de estar num disco que o Windows enxerga (C:, um
  pendrive). Se tiver uma partição Linux no mesmo computador, o Windows não
  a lê: copie os PDFs (e a subpasta `transcriptions`, se já houver) para o
  lado do Windows.
- **Placa NVIDIA**: a janela diz qual placa há. Com o driver 580 ou mais
  novo, a instalação já põe os leitores de GPU (uns 35 s por página em vez
  de uns 3 min); numa instalação antiga, de processador, o botão **Instalar
  os leitores de GPU** troca-os na mesma pasta `.venv-ocr`. **Ler usando**
  escolhe placa ou processador. Placas AMD e Intel ainda não são usadas
  (relatório `docs/WINDOWS-TEST-2026-10-17.md`, §5).
- **Desinstalar**: Verificar a instalação → Desinstalar… apaga `.venv-ocr` e
  pergunta pelo modelo; depois, apague a pasta do programa. Os PDFs e as
  subpastas `transcriptions` não são tocados.
- Há também um instalador nativo por fazer: `installer/Desembarque.iss`
  (Inno Setup), ainda não compilado — veja `installer/README.md`.
- Testado no Windows 11 em 2026-10-17 com a versão anterior (relatório em
  `docs/WINDOWS-TEST-2026-10-17.md`); o `.bat` que instala o Python e os
  leitores de GPU ainda não foram vistos rodar no Windows: se algo falhar,
  copie o texto da caixa da janela e mande para quem lhe passou o programa.

### macOS

- Python: https://www.python.org/downloads/ (3.12). O instalador da
  python.org traz o Tk que a janela usa; o Python que vem com o sistema
  pode não trazer.
- Abra **`Desembarque.command`** com dois cliques. Na primeira vez o macOS
  pode recusar ("não pode ser aberto porque é de um desenvolvedor não
  identificado"): clique com o botão direito no arquivo → **Abrir** → Abrir.
  Se disser que não tem permissão, no Terminal, dentro da pasta:
  `chmod +x Desembarque.command`.
- Ainda não foi testado num Mac.

### Linux

- Python 3 costuma já estar; faltam às vezes o Tk e o venv. No
  Debian/Ubuntu/Mint: `sudo apt install python3 python3-venv python3-tk`;
  no Fedora: `sudo dnf install python3 python3-tkinter`.
- Abra **`Desembarque.sh`** com dois cliques (o gerenciador de arquivos pode
  perguntar "Executar" — sim) ou, no terminal, dentro da pasta:
  `sh Desembarque.sh`. Se não abrir por falta de permissão:
  `chmod +x Desembarque.sh`.
- Com placa NVIDIA (driver 580+): a instalação põe os leitores de GPU na
  mesma pasta `.venv-ocr`; **Ler usando** escolhe placa ou processador.
- Testado no Linux (KDE, Ubuntu-like).
