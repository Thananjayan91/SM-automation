# AI Social Publisher — Mobile Companion App (React Native + Expo)

A cross-platform React Native + Expo companion application designed for mobile content capture, real-time AI post generation tracking, and 1-tap version approval.

## 🚀 Key Features

1. **Authentication & Multi-Tenant Workspaces**:
   - Work email & password authentication matching web SaaS credentials.
   - Dynamic workspace selector passing `X-Tenant-ID` header on all API requests.
   - Configurable Backend Host URL (supporting Android Emulator `10.0.2.2:5000` or local Wi-Fi `http://<LAN_IP>:5000`).

2. **Mobile Quick Capture & AI Studio**:
   - Submit quick topic prompts or web article URLs.
   - Select tone presets (*Authoritative & Insightful*, *Casual & Conversational*, *Direct & Punchy*, *Inspirational*).
   - Enter custom creative guidance and trigger asynchronous pipeline dispatch.

3. **Live AI Generation Tracker**:
   - Real-time polling of backend generation job (`GET /api/v1/jobs/<id>`).
   - Animated visual step progression:
     - 🔍 Angle & Topic Extraction
     - 📚 Deep Research & Citations
     - ✍️ Copy & Hashtag Synthesis
     - 🎨 1080x1080 Branded Banner Rendering (Pillow engine)
   - One-tap transition to post review once completed.

4. **Post Feed & Status Filters**:
   - Fast filter tabs: *All*, *In Review*, *Approved*, *Published*, *Drafts*.
   - Search bar filtering by caption content or hashtags.
   - Pull-to-refresh synchronization.

5. **Review & 1-Tap Version Approval**:
   - High-fidelity social preview card (banner graphic, formatted caption, hashtags, and first comment automation).
   - Publishing target account chips with delivery status.
   - **One-Tap Version Approval**: Signs off the exact immutable snapshot (`v1`, `v2`, etc.) via `POST /api/v1/posts/<id>/approve`, locking content for scheduling and auto-publishing.

---

## 📱 Project Structure

```
mobile/
├── package.json
├── app.json
├── tsconfig.json
├── babel.config.js
├── App.tsx                     # App entry point with SafeArea & AuthProvider
└── src/
    ├── api/
    │   ├── client.ts           # Central fetch client with session & X-Tenant-ID headers
    │   ├── auth.ts             # Login & Logout REST endpoints
    │   ├── posts.ts            # Posts list, detail, and 1-tap version approval
    │   └── generator.ts        # Source submission, generate trigger, and job polling
    ├── constants/
    │   └── theme.ts            # Palette, typography, and spacing
    ├── context/
    │   └── AuthContext.tsx     # User auth state, active workspace, and server config
    ├── navigation/
    │   └── index.tsx           # React Navigation stack & bottom tabs
    ├── components/
    │   ├── PostCard.tsx        # Post feed summary card
    │   └── StatusBadge.tsx     # Status pill badge
    ├── screens/
    │   ├── LoginScreen.tsx             # Auth & server URL setup
    │   ├── PostsListScreen.tsx         # Filterable library feed
    │   ├── QuickCaptureScreen.tsx      # Topic/URL capture & AI generator trigger
    │   ├── GenerationProgressScreen.tsx# Real-time multi-step progress bar
    │   ├── PostDetailScreen.tsx        # Social preview & 1-tap approval
    │   └── WorkspaceScreen.tsx         # Workspace switch & user settings
    └── types/
        └── index.ts            # Shared TypeScript contracts
```

---

## 🛠️ How to Run Locally

### Prerequisites
- Node.js v18+ and npm
- Python Flask backend running on `http://127.0.0.1:5000` (or `http://localhost:5000`)
- Expo Go app on your physical Android phone (or an Android Emulator / iOS Simulator)

### 1. Start the Backend Dev Server
From the root workspace directory:
```bash
python backend/wsgi.py
```

### 2. Start Expo Metro Bundler
From the `mobile/` directory:
```bash
cd mobile
npm start
```

### 3. Open on Android Device
- **Physical Device**: Scan the QR code shown in the terminal with the **Expo Go** Android app. In the app login screen, set the Backend API Host to your machine's local Wi-Fi IP address (e.g. `http://192.168.1.50:5000`).
- **Android Emulator**: Press `a` in the terminal to launch on the running emulator. The default host `http://10.0.2.2:5000` will automatically route to your host machine's `http://127.0.0.1:5000`.
