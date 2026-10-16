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
6. **Ligar**. Inicia o programa que lê os PDFs (1 a 2 minutos carregando), o
   navegador abre sozinho na página do Desembarque e a pasta começa a ser
   lida; a janela diz em que documento está, quantos faltam e quanto tempo.
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

- Python: https://www.python.org/downloads/ (3.12). No instalador, marque
  **Add python.exe to PATH**. O Python da Microsoft Store também serve.
- Abra **`Desembarque.bat`** com dois cliques. Se aparecer "Python nao
  encontrado", o Python não está no PATH: reinstale marcando a opção acima.
- A pasta dos PDFs tem de estar num disco que o Windows enxerga (C:, um
  pendrive). Se tiver uma partição Linux no mesmo computador, o Windows não
  a lê: copie os PDFs (e a subpasta `transcriptions`, se já houver) para o
  lado do Windows.
- Os leitores instalados são os de CPU. Com placa NVIDIA e vontade de usá-la,
  os comandos para trocar pelos de GPU estão em `requirements-kraken.txt`.
- Ainda não foi testado no Windows: se algo falhar, copie o texto da caixa
  da janela e mande para quem lhe passou o programa.

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
- Com placa NVIDIA: os leitores de GPU vão na mesma pasta `.venv-ocr`; os
  comandos estão em `requirements-kraken.txt`. O programa usa a placa sozinho
  quando ela está lá e a CPU quando não está.
- Testado no Linux (KDE, Ubuntu-like).
