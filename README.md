# Ksnip Viewer

Preview de imagens com edição rápida para Linux/GNOME, inspirado no fluxo do Ksnip: abrir, marcar e copiar para o cliente.

Projeto independente, sem afiliação com o Ksnip.

## Executar

Requer Python 3, GTK 3, PyGObject, Pillow, integração Cairo e GdkPixbuf. No Ubuntu/Debian:

```sh
sudo apt install python3-gi python3-cairo python3-gi-cairo python3-pil gir1.2-gtk-3.0
git clone https://github.com/sergioelisan/ksnip_viewer.git
cd ksnip_viewer
python3 -m ksnip_viewer /caminho/screenshot.png
```

Sem arquivo, abre uma janela com o botão **Abrir**. Também aceita URI `file://` na integração D-Bus. A orientação EXIF é aplicada ao abrir. Salvar mantém a resolução da imagem, independentemente do zoom; **Salvar como…** exporta PNG.

## Edição

Arraste sobre a imagem para desenhar. Texto é inserido com um clique. O recorte é aplicado ao soltar o mouse e pode ser desfeito. Cor e espessura ficam na barra superior.

A seta é a primeira ferramenta e fica selecionada por padrão ao abrir uma imagem, com espessura inicial de 8 pixels.

Para indicar etapas, selecione **①** (atalho **N**) e clique nos pontos da imagem: cada clique coloca um círculo com o próximo número, começando em 1. Cor e espessura controlam a cor e o tamanho do marcador. A sequência é independente por imagem; desfazer um marcador recupera seu número para o próximo clique, e refazer restaura o marcador e a sequência. Os círculos aparecem tanto na imagem copiada quanto no PNG salvo.

| Atalho | Ação |
| --- | --- |
| V / A / R / E | Visualizar / seta / retângulo / elipse |
| P / T / X | Desenho livre / texto / recortar |
| N | Círculos numerados incrementais |
| Ctrl+Z / Ctrl+Shift+Z | Desfazer / refazer |
| Ctrl+C | Copiar a imagem com as marcações |
| Ctrl+S | Salvar diretamente no arquivo aberto, sem confirmação de sobrescrita |
| Ctrl+O | Abrir outra imagem |
| Ctrl++ / Ctrl+- | Aumentar / diminuir zoom |
| Espaço / Esc | Fechar sem salvar e sem confirmação |

**Ctrl+S sobrescreve o arquivo aberto**, mantendo seu formato. Para preservar o original, use o botão **Salvar como…**, que sugere `nome-marcada.png`. Fechar ou abrir outra imagem descarta alterações não salvas, sem confirmação. A persistência da área de transferência depois de encerrar depende do gerenciador de clipboard do desktop.

## Nautilus: abrir pelo Espaço

O Nautilus usa um único serviço de preview para todos os tipos de arquivo. Este projeto implementa o contrato D-Bus do Sushi, incluindo a interface do GNOME 50 com token de ativação e a interface legada. O schema é obtido do Sushi instalado quando disponível.

```sh
# Apenas entrada no menu de aplicativos / Abrir com:
python3 scripts/install.py

# Também assumir o preview pelo Espaço:
python3 scripts/install.py --space-preview
```

Depois de instalar, encerre e entre novamente na sessão para que o serviço anterior deixe o barramento. No Nautilus, selecione uma imagem e pressione Espaço. Pressione novamente para fechar.

**A integração pelo Espaço substitui o Sushi para toda a sessão do usuário. Esta versão só visualiza imagens locais compatíveis com Pillow; PDFs, vídeos, pastas e arquivos remotos não têm preview.** Instale sem `--space-preview` se precisar manter esses previews no Sushi. GIFs são abertos como imagem estática. Esta versão não inclui seleção/edição de marcas já desenhadas; use desfazer/refazer.

O instalador grava apenas em `$XDG_DATA_HOME` (por padrão `~/.local/share`), preserva um serviço personalizado anterior em backup e aponta para esta pasta. Mantenha o projeto no mesmo caminho. Para remover e restaurar o preview anterior:

```sh
python3 scripts/install.py --uninstall
```

Encerre e entre na sessão após remover também. Nenhuma alteração global é necessária.

## Atualizar

Salve as imagens que quiser manter e execute dentro da pasta do projeto:

```sh
git pull --ff-only
pkill -f '[k]snip-viewer.*--preview-service'
```

Ao pressionar Espaço novamente, o Nautilus inicia o serviço atualizado. Não é preciso reinstalar.

## Verificação

```sh
python3 -m unittest discover -s tests -v
python3 -m compileall -q ksnip_viewer scripts
```

Os testes verificam exportação, pixels das marcações, preservação do original, recorte e histórico. A conferência final de foco/ativação no Wayland, clipboard e tecla Espaço deve ser feita em uma sessão GNOME real.

## Licença

GNU General Public License versão 2 (GPL-2.0-only). Veja [LICENSE](LICENSE).
