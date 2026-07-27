#!/bin/bash

# 1. Adiciona as alterações
git add .

# 2. Captura as mudanças staged para enviar ao opencode
DIFF=$(git diff --cached)

# Se não houver nada alterado, interrompe o script
if [ -z "$DIFF" ]; then
  echo "Nenhuma alteração encontrada para commit."
  exit 0
fi

echo "Gerando descrição com opencode..."

# 3. Usa o comando 'run' correto passando o diff e as instruções
COMMIT_MSG=$(opencode run "Com base nas mudanças a seguir, gere uma única linha de mensagem de commit no padrão Conventional Commits (ex: feat: ..., fix: ...). Não inclua formatação de código Markdown, texto explicativo ou quebras de linha, retorne APENAS o texto puro do commit. Mudanças: $DIFF")

# 4. Valida se a mensagem foi gerada
if [ -z "$COMMIT_MSG" ]; then
  echo "Erro: O opencode não retornou uma mensagem. Commit cancelado."
  git commit -m "update"
fi

echo "----------------------------------------"
echo "Mensagem gerada: $COMMIT_MSG"
echo "----------------------------------------"

# 5. Executa o commit e o push
git commit -m "$COMMIT_MSG"
git push
