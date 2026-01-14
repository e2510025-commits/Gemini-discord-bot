# Gemini Discord Bot + Dashboard

このリポジトリは、Discord Bot (Python) と Next.js ダッシュボードを統合したプロジェクトの雛形です。

## 構成
- `/bot`: Discord bot、FastAPIでAPIを提供
- `/web`: Next.jsアプリ（App Router）
- `/shared`: SQLAlchemyモデル

## 使い方（簡易）

### Bot
1. cd bot
2. python -m venv .venv && source .venv/bin/activate
3. pip install -r requirements.txt
4. `.env` を作成（`.env.example` を参照）
5. APIサーバ起動: `uvicorn bot.api:app --reload --port 8000`
6. Bot起動: `python main.py`

### Web
1. cd web
2. npm install
3. npm run dev

## 注意点
- GeminiのSDKは `google-generative-ai` を利用する想定です。APIキーを`.env`に設定してください。
- SSEを使用してリアルタイムイベントを配信します。プロダクションでは適切な認証や認可を追加してください。

## Prisma (optional)
このプロジェクトでは、Web側から高速にDBを読み取るために `Prisma` を使うことを想定しています。`/web/prisma/schema.prisma` に開発用のスキーマを配置しています。実行例:

1. cd web
2. npm install -D prisma
3. npx prisma generate
4. npx prisma db push --preview-feature

PrismaはSQLiteの `DATABASE_URL` を読み取るので、`.env` を設定してください（同じDBを参照する場合はBotの `DATABASE_URL` と一致させます）。
## Music / Web Playback (Hybrid)
- Bot は Discord VC 再生（yt-dlp + FFmpeg）をサポートします。`/play, /skip, /stop, /recommend` を実装済みです。
- Web ダッシュボードは Socket.IO を介して再生状態を同期し、Web Audio API を使った高音質再生が可能です（`/api/music/stream?track_id=<id>` で音声URLへリダイレクト）。
- 同時視聴（Listen Along）や VC/Web の切替は Socket.IO イベントで同期します。開発/本番での著作権・配信ポリシーを必ず確認してください。
