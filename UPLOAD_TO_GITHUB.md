# GitHubへのアップロード手順

対象リポジトリ:

```text
https://github.com/conlab-clbs/clbs-slidevideo-edit
```

## 画面からアップロードする方法

1. GitHubの `clbs-slidevideo-edit` リポジトリを開く
2. `Add file` を押す
3. `Upload files` を押す
4. このフォルダの中身をアップロードする

アップロードする中身:

```text
README.md
install.py
UPLOAD_TO_GITHUB.md
clbs-slidevideo-edit/
```

既存の `README.md` は上書きしてOK。

## アップロード後に確認すること

GitHub上に次が見えればOK。

```text
README.md
install.py
clbs-slidevideo-edit/SKILL.md
clbs-slidevideo-edit/scripts/build_slidevideo.py
clbs-slidevideo-edit/references/input_format.md
```

## 受講生に渡す文面

```text
CodexまたはClaude Codeに以下を貼ってください。

このGitHubリポジトリから clbs-slidevideo-edit を導入してください。

https://github.com/conlab-clbs/clbs-slidevideo-edit

私の環境がCodexかClaude Codeかを確認して、適切なskillsフォルダにインストールしてください。
既存版がある場合は上書きしてください。
必要なPython依存関係とffmpegも確認してください。
インストール後、CodexまたはClaude Codeを再起動する必要があることを案内してください。
```
