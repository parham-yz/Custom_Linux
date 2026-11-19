# Orca on Linux: PDF viewer, plugins, and annotation/review options

**Research snapshot:** 2026-08-13. This is the **Stably/Lovecast Orca ADE** (`stablyai/orca`), not GNOME's Orca screen reader. Findings below are based on Orca's public `main` branch at commit [`e84fb46`](https://github.com/stablyai/orca/commit/e84fb46eafb177b7be0f243a546cd30d6070309b), its public docs/issues, and inspection of the installed Linux AppImage v1.4.180. Orca changes very quickly, so source permalinks are used where possible.

## Executive answer

- Orca is an open-source, cross-platform **Electron + React + TypeScript** application. The desktop has Electron main/preload/renderer layers; a long-lived daemon/runtime and RPC surface own terminals/worktrees/automation; the repo also contains a headless server, web renderer, SSH relay, native helpers, and a separate mobile companion.
- Linux is a first-class target (x64/arm64 AppImage; the repo's build script also produces a `.deb`). The installed AppImage is conventional Electron packaging: `app.asar`, unpacked child-process entry points/native modules, Chromium, and an embedded Node-based CLI.
- Orca now has a real but explicitly **experimental plugin API v1** and an official Git marketplace. Plugins can contribute right-sidebar panels, commands, keybindings, language packs, VM recipes, and agent profiles. Worker code runs out of process in Node; panel HTML is sandboxed and calls a small capability-gated host API.
- The current plugin surface **cannot replace/extend a file viewer and cannot read or write the focused PDF**. Its workspace API exposes only display name, branch, and terminal IDs. Therefore PDF annotation is not realistically an install-only plugin today; it needs an upstream host extension point/API or a source contribution.
- The built-in PDF viewer is not Chromium's PDF viewer. It is a custom React component around **Mozilla PDF.js (`pdfjs-dist` 6.x)**. PDF bytes arrive as base64, are decoded into a `Uint8Array`, and are passed to `pdfjsLib.getDocument`; PDF.js `PDFViewer`, `PDFLinkService`, `PDFFindController`, and a separate worker render the document. Present UI provides scrolling, selectable text, find, zoom/fit-width, and session-only scroll restoration. There is no annotation toolbar, review-note overlay, or save path in `PdfViewer.tsx`.
- Best product fit: add **non-destructive PDF review notes** to core Orca first (page + normalized rectangle/quads + selected-text quote + PDF fingerprint, stored in Orca review state and batch-sendable to an agent). Optionally add a second phase using PDF.js's annotation editor and `PDFDocumentProxy.saveDocument()` for highlights/free text/ink embedded into the PDF. A Linux external-viewer fallback (Okular/Xournal++) is low effort but provides a weaker Orca-to-agent review loop.

## 1. Product and architecture

### Public product description

The public repository describes Orca as an ADE for running CLI agents side-by-side, each in an isolated Git worktree, with desktop/mobile/VPS support:

- Repository/readme: <https://github.com/stablyai/orca>
- Product/docs: <https://www.onorca.dev/docs>
- Parallel worktree model: <https://www.onorca.dev/docs/model/worktrees>
- Linux/macOS/Windows downloads and releases: <https://github.com/stablyai/orca/releases>
- Source contribution/build instructions: <https://github.com/stablyai/orca/blob/e84fb46eafb177b7be0f243a546cd30d6070309b/.github/CONTRIBUTING.md>
- MIT license: <https://github.com/stablyai/orca/blob/e84fb46eafb177b7be0f243a546cd30d6070309b/LICENSE>

The repo is public and TypeScript-heavy, so modifying the core viewer is feasible without reverse engineering. The readme's development path is `pnpm install`, `pnpm dev`; CI-quality checks are `pnpm lint`, `pnpm typecheck`, `pnpm test`, and `pnpm build`.

### Desktop layers

Evidence in the build configuration and tree supports this high-level model:

1. **Electron main process** (`src/main`) owns app/window lifecycle, filesystem and Git operations, PTYs, SSH, browser integration, updates, persistence, plugins, and the runtime RPC server.
2. **Preload** (`src/preload`) exposes typed IPC calls rather than enabling Node directly in the UI.
3. **React renderer** (`src/renderer`) provides editors/viewers, worktree UI, terminals, review UI, browser panes, settings, etc. Vite produces main renderer, dashboard popout, and web entries.
4. **Shared contracts** (`src/shared`) are intentionally Electron-free in many cases so desktop, daemon/headless runtime, relay, CLI, and tests agree on types and validation.
5. **Long-lived daemon/runtime and CLI.** Packaged child entry points include `daemon-entry`, plugin host, computer sidecar, watcher process, and workers. The installed app publishes a runtime descriptor with Unix-socket and loopback-WebSocket transports; the packaged `orca` CLI talks to that runtime rather than scraping UI state.
6. **Remote/web/mobile.** `src/relay` supports remote/SSH operation, the renderer has a web entry, and `mobile/` is a separate companion. This matters because any PDF write/review API should work for local, SSH, remote-runtime, and web contexts rather than directly calling local `fs` from the renderer.
7. **Native helpers** exist under `native/` for computer use and platform integration.

Credible source links:

- Electron/Vite entry points and bundled child processes: <https://github.com/stablyai/orca/blob/e84fb46eafb177b7be0f243a546cd30d6070309b/electron.vite.config.ts#L194>
- App dependencies/scripts/platform build targets: <https://github.com/stablyai/orca/blob/e84fb46eafb177b7be0f243a546cd30d6070309b/package.json>
- Main entry/service wiring: <https://github.com/stablyai/orca/blob/e84fb46eafb177b7be0f243a546cd30d6070309b/src/main/index.ts>
- Headless Linux guide: <https://github.com/stablyai/orca/blob/e84fb46eafb177b7be0f243a546cd30d6070309b/docs/reference/headless-linux-server.md>
- CLI docs: <https://www.onorca.dev/docs/cli/overview>
- SSH docs: <https://www.onorca.dev/docs/ssh>

### Linux packaging observed locally

The installed v1.4.180 ARM64 AppImage contains the Electron executable, Chromium resources, `resources/app.asar` (~127 MB), and `app.asar.unpacked/out/...` child-process code. The running process tree has Electron browser/renderer/GPU/network processes plus Orca's daemon, file watcher, and computer sidecar. The same release is also available as x64 AppImage. This agrees with the public `build:linux` script (`electron-builder ... --linux AppImage deb`).

This is useful operationally: a source patch should be built through Orca's normal Electron toolchain, not by trying to inject JavaScript into `app.asar`. AppImage patching is possible for a private prototype but is brittle across Orca's frequent releases.

## 2. Plugin/extension support

### What exists now

The current manifest is `orca-plugin.json`, `manifestVersion: 1`, `pluginApi: 1`, with identity `<publisher>.<id>` and an Orca minimum version. Contributions currently include:

- sandboxed right-sidebar **panels** (HTML entry),
- **commands** (declarative built-in action aliases or worker handlers),
- worktree/agent-status **event subscriptions**,
- **language packs**,
- **keybindings**,
- **VM recipes**,
- **agent profiles**.

The source itself warns that the system is experimental and has no compatibility promises until plugin API v1 freezes:

- Manifest contract: <https://github.com/stablyai/orca/blob/e84fb46eafb177b7be0f243a546cd30d6070309b/src/shared/plugins/plugin-manifest.ts#L22-L33>
- Contributions/capabilities schema: <https://github.com/stablyai/orca/blob/e84fb46eafb177b7be0f243a546cd30d6070309b/src/shared/plugins/plugin-manifest.ts#L91-L132>
- Example plugin manifest: <https://github.com/stablyai/orca/blob/e84fb46eafb177b7be0f243a546cd30d6070309b/examples/plugins/hello-orca/orca-plugin.json>
- Example worker: <https://github.com/stablyai/orca/blob/e84fb46eafb177b7be0f243a546cd30d6070309b/examples/plugins/hello-orca/main.mjs>
- Example sandboxed panel: <https://github.com/stablyai/orca/blob/e84fb46eafb177b7be0f243a546cd30d6070309b/examples/plugins/hello-orca/panel.html>

### Runtime/security model

- A plugin `main` module is imported in a **separate plain-Node child process** and receives command/event/host-call/log APIs. It is lazily activated and supervised; failures do not need to crash the Electron renderer.
- The worker environment is allowlisted/scrubbed, but this is **crash/process isolation, not a Node sandbox**: approved worker code can use Node facilities available to it. The host's Orca-specific methods are independently capability checked.
- Panels are HTML in a sandboxed, opaque-origin iframe (`allow-scripts`), communicate through validated `postMessage` messages, and have rate/size/watchdog controls. Main rechecks identity, method parameters, consent, and capability.
- Newly discovered plugins require consent and can be disabled. Marketplace installs are content-addressed/pinned and the installer does not run install scripts.

Sources/discussion:

- Worker runtime/API: <https://github.com/stablyai/orca/blob/e84fb46eafb177b7be0f243a546cd30d6070309b/src/main/plugins/plugin-host-runtime.ts>
- Scrubbed worker environment: <https://github.com/stablyai/orca/blob/e84fb46eafb177b7be0f243a546cd30d6070309b/src/main/plugins/plugin-worker-env.ts>
- Panel protocol/security notes: <https://github.com/stablyai/orca/blob/e84fb46eafb177b7be0f243a546cd30d6070309b/src/shared/plugins/plugin-panel-bridge.ts>
- Initial plugin design discussion (historical; some trust/design details changed before implementation): <https://github.com/stablyai/orca/pull/5738>
- Out-of-process host/panel/consent implementation discussion: <https://github.com/stablyai/orca/pull/7506>
- Marketplace lifecycle/security discussion: <https://github.com/stablyai/orca/pull/8548>

### Marketplace/distribution

There is an official Git-backed marketplace index and several small public plugin repositories:

- Marketplace repo/index: <https://github.com/stablyai/orca-plugins/blob/main/orca-marketplace.json>
- Navigation shortcuts plugin: <https://github.com/stablyai/orca-navigation-shortcuts>
- Midnight theme: <https://github.com/stablyai/orca-midnight-theme>
- Workflow skills: <https://github.com/stablyai/orca-workflow-skills>

The current official index contains themes, workflow skills, language, icons, terminal theme, VM recipe, and navigation/keybinding plugins. It does not contain a PDF plugin.

### Why a PDF viewer plugin is blocked today

The current capability kinds are only `workspace:read`, `terminal:send`, notifications, plugin storage/secrets, event subscriptions, and plugin-owned settings:

- Capability list: <https://github.com/stablyai/orca/blob/e84fb46eafb177b7be0f243a546cd30d6070309b/src/shared/plugins/plugin-capabilities.ts#L15-L25>
- Host API: <https://github.com/stablyai/orca/blob/e84fb46eafb177b7be0f243a546cd30d6070309b/src/shared/plugins/plugin-host-api.ts#L122-L254>

`workspace.readContext` exposes branch, display name, and terminal IDs—**not active file, worktree path, file bytes, writes, editor/viewer registration, review-note APIs, or an agent-prompt/review dispatch API**. The only typed extension point currently implemented is a worker command. The manifest has no `viewers`, `editors`, `customEditors`, or MIME/file-pattern contribution.

Consequences:

- A panel could display a PDF only if it independently obtained bytes, but the sandboxed panel has no file bridge and no focused-file identity.
- A Node worker has broad Node ability after consent, but no reliable product contract telling it which worktree/file/tab is focused, and no built-in worker-to-panel application bridge for a custom editor workflow.
- A plugin cannot intercept `.pdf` opens or replace `PdfViewer`.
- Doing this properly as a plugin first requires upstream additions such as `contributes.fileViewers`, focused-file/open-file events, bounded binary read/write APIs with local/SSH parity, and review-note/agent-dispatch hooks.

Thus **core contribution/fork is the feasible path now**. A plugin architecture could be proposed upstream, but it is more work than adding annotation directly to the existing PDF.js component.

## 3. Current PDF viewer implementation

### User-visible behavior

Official docs promise PDF scroll, zoom, text selection, and session-only scroll restoration:

- Viewer docs: <https://www.onorca.dev/docs/editing/viewers>
- Rich repo previews are also advertised in the readme: <https://github.com/stablyai/orca#features>

The source adds find-in-PDF, fit-to-width, zoom bounds (25%–500%), error handling for malformed/password-protected PDFs, and separate session-position keys where appropriate.

### Data/rendering path

The implementation is a custom PDF.js viewer:

1. `ImageViewer.tsx` recognizes MIME `application/pdf` and renders `PdfViewer`.
2. The file-content API supplies the binary as base64 text.
3. `PdfViewer.tsx` removes whitespace, uses `window.atob`, creates `Uint8Array`, and calls `pdfjsLib.getDocument({data: bytes})`.
4. It constructs PDF.js `EventBus`, `PDFLinkService`, `PDFFindController`, and `PDFViewer` from `pdfjs-dist/web/pdf_viewer.mjs`.
5. It enables the text layer (`textLayerMode: 1`) and imports the PDF.js viewer CSS and a bundled `pdf.worker.min.mjs` worker.
6. Orca's own React toolbar drives zoom/find. View positions are stored in an in-memory LRU as PDF user-space page/top/left coordinates rather than fragile pixels.

Source:

- Current viewer imports/setup: <https://github.com/stablyai/orca/blob/e84fb46eafb177b7be0f243a546cd30d6070309b/src/renderer/src/components/editor/PdfViewer.tsx#L1-L21>
- PDF.js viewer construction: <https://github.com/stablyai/orca/blob/e84fb46eafb177b7be0f243a546cd30d6070309b/src/renderer/src/components/editor/PdfViewer.tsx#L90-L124>
- Byte loading: <https://github.com/stablyai/orca/blob/e84fb46eafb177b7be0f243a546cd30d6070309b/src/renderer/src/components/editor/PdfViewer.tsx#L238-L262>
- PDF MIME routing: <https://github.com/stablyai/orca/blob/e84fb46eafb177b7be0f243a546cd30d6070309b/src/renderer/src/components/editor/ImageViewer.tsx>
- Scroll-position implementation: <https://github.com/stablyai/orca/blob/e84fb46eafb177b7be0f243a546cd30d6070309b/src/renderer/src/components/editor/pdf-view-position.ts>

The installed v1.4.180 AppImage corroborates this: it contains `pdf.worker.min-*.mjs` and the bundled viewer code rather than relying on Chromium's internal PDF extension.

### What is absent

At this snapshot, `PdfViewer.tsx` has no:

- PDF.js annotation-editor mode,
- highlight/free-text/ink/stamp toolbar,
- Orca review-note controls,
- persistence for notes/annotation storage,
- call to `PDFDocumentProxy.saveDocument()`,
- binary write-back/atomic replace workflow,
- batch “send PDF review notes to agent” workflow.

Text selection being supported does **not** imply annotation is supported.

### Relevant issue/PR history

- PDF search was added in PR #899 (the implementation later evolved from Electron webview to direct PDF.js): <https://github.com/stablyai/orca/pull/899>
- Zoom persistence: <https://github.com/stablyai/orca/issues/10165> and <https://github.com/stablyai/orca/pull/10168>
- Tab switch reset report: <https://github.com/stablyai/orca/issues/10352>
- Session scroll restoration and its known limits: <https://github.com/stablyai/orca/pull/12163>
- No matching public issue specifically requesting PDF annotation was found in GitHub issue search at this snapshot. A related Office-document request explicitly asks for selection/annotation/agent review: <https://github.com/stablyai/orca/issues/8301>

## 4. Feasible PDF annotation/review approaches

### Option A — Core, non-destructive “PDF review notes” (recommended first)

**Goal:** match Orca's strong existing code-diff and Markdown review loop without modifying the PDF bytes.

Suggested annotation record:

```ts
type PdfReviewAnchor = {
  filePath: string
  documentFingerprint: string       // PDF.js fingerprint and/or content hash
  pageNumber: number                // 1-based
  rects: Array<{ x: number; y: number; width: number; height: number }>
  selectedText?: string             // quote fallback/re-anchoring
  color?: string
}
```

Coordinates should be **normalized PDF-page coordinates**, not viewport pixels. Convert browser selection rectangles from the PDF.js text layer through the page viewport. This survives zoom, pane resize, and scrolling and mirrors the reasoning behind Orca's existing user-space scroll restoration. Store a text quote and short prefix/suffix for best-effort re-anchoring when the PDF changes.

UX:

1. Select text or drag a region on a PDF page.
2. `Add review note` opens the same style composer used by Markdown/diff review.
3. Overlay highlights and note badges on each PDF.js page; click to inspect/reply/resolve.
4. “Send notes to agent” emits a batch such as `report.pdf, page 7, quote: “...”: <comment>` and optionally attaches a cropped page screenshot.
5. Store notes in Orca workspace/session review state, not in the PDF. Warn/mark stale if the PDF fingerprint changes.

Why this is the best first increment:

- no binary PDF rewrite/corruption risk;
- review comments remain Orca workflow data and can be resolved/replied/batch-sent;
- works with read-only PDFs;
- can be designed for local/SSH/remote parity because only note state is written;
- reuses the existing review-note model/UI from code/Markdown rather than recreating an office annotation suite.

Relevant existing review behavior to reuse:

- Annotate AI Diff docs: <https://www.onorca.dev/docs/review/annotate-ai-diff>
- Markdown selection annotations: <https://www.onorca.dev/docs/editing/markdown>
- Current Markdown annotation renderer: <https://github.com/stablyai/orca/blob/e84fb46eafb177b7be0f243a546cd30d6070309b/src/renderer/src/components/editor/MarkdownPreview.tsx>

**Estimated complexity:** medium. Main work is robust selection-to-page coordinate conversion, page overlay lifecycle/virtualization, comment state schema, and batch prompt formatting. It is still materially smaller and safer than a general plugin viewer API or embedded PDF mutation.

### Option B — Enable PDF.js native annotation editing and save into the PDF

PDF.js already has an annotation editor layer. Its viewer supports an `annotationEditorMode`; upstream implements free text, ink, highlights, stamps/signatures depending on version/configuration, undo/redo, and uses `PDFDocumentProxy.saveDocument()` to produce updated bytes.

Credible upstream references:

- PDF.js repository: <https://github.com/mozilla/pdf.js>
- `PDFViewer` annotation-editor option/manager source: <https://github.com/mozilla/pdf.js/blob/master/web/pdf_viewer.js>
- Annotation editor manager source: <https://github.com/mozilla/pdf.js/blob/master/src/display/editor/tools.js>
- Official viewer save path (`pdfDocument.saveDocument()`): <https://github.com/mozilla/pdf.js/blob/master/web/app.js>
- PDF.js examples: <https://mozilla.github.io/pdf.js/examples/>

Required Orca work:

1. Instantiate/configure PDF.js annotation editor support and add Orca toolbar buttons (highlight/free text/ink/undo/redo).
2. Keep the document proxy and annotation storage alive in React state/refs.
3. On Save, call `await pdfDocument.saveDocument()` and atomically write the returned bytes.
4. Add a **binary** file-write IPC/runtime contract. Orca's normal `fs:writeFile` path is UTF-8 text; do not smuggle a PDF through it. The contract must support local, SSH, remote runtime, file authorization, expected-host checks, temporary sibling file + fsync/rename where supported, and conflict detection if the agent changed the PDF while it was open.
5. Suppress/reconcile the file watcher reload caused by Orca's own save and preserve scroll/zoom.
6. Handle document permissions, encrypted PDFs, signatures, XFA, very large documents, malformed annotation dictionaries, and save failure/recovery.
7. Add before-save backup or a Save As option until mature.

**Estimated complexity:** medium-high. PDF.js provides much of the editor but robust cross-host file persistence, conflict handling, and polish remain Orca work.

This gives portable annotations visible in other PDF viewers, but is less naturally aligned with Orca's reply/resolve/batch-agent review model. A hybrid is attractive: Orca review comments stored separately, with an explicit “Export highlights/comments into PDF” action.

### Option C — Custom overlay library, still core

A library such as `react-pdf-highlighter` demonstrates selection, area highlights, popovers, and coordinate transforms over PDF.js:

- <https://github.com/agentcooper/react-pdf-highlighter>

It can accelerate a prototype, but Orca already owns a direct PDF.js viewer, scroll-position logic, and review-note UI. Integrating the underlying ideas (scaled positions and page overlays) may be safer than adopting a second viewer abstraction with its own PDF.js version/lifecycle. Check license, PDF.js-version compatibility, React 19 behavior, bundle size, accessibility, and 5,000-page behavior before adding it.

### Option D — External Linux annotator (fast fallback)

For an immediate personal workflow:

- launch the worktree PDF with **Okular** (highlights, popup notes, shapes/stamps) or **Xournal++** (pen/highlighter/free text),
- save annotations into/alongside the PDF,
- let Orca's file watcher reload the changed file,
- ask an agent to inspect/extract annotations with a PDF tool or export a comment summary.

This is viable today from an Orca terminal with `xdg-open file.pdf`, `okular file.pdf`, or `xournalpp file.pdf`. It is local-Linux-only unless remote files are first downloaded. Embedded annotations also produce opaque/binary Git diffs and may be difficult for an agent to map into a structured review conversation.

There are active upstream proposals to expose a first-class default/Open With action:

- Open in default app issue: <https://github.com/stablyai/orca/issues/11252>
- Corresponding PR: <https://github.com/stablyai/orca/pull/11268>
- OS-registered Open With issue: <https://github.com/stablyai/orca/issues/13993>
- Cross-platform Open With PR: <https://github.com/stablyai/orca/pull/13994>

Do not assume those open PRs are present in the installed stable build.

### Option E — New plugin extension points (strategic, not quickest)

If third-party document viewers are a product goal, propose:

```json
"contributes": {
  "fileViewers": [{
    "id": "pdf-review",
    "patterns": ["**/*.pdf"],
    "mimeTypes": ["application/pdf"],
    "entry": "viewer.html",
    "priority": 10
  }]
}
```

The host would need:

- active-file/open/close/change events;
- authorized, bounded, streaming binary reads;
- atomic binary write/Save As with local/SSH/remote parity;
- a full-size custom editor surface (not only a narrow right-sidebar iframe);
- lifecycle/dirty/conflict/save semantics;
- optional review-note and agent-dispatch APIs;
- clear trust/consent, CSP, resource URLs, memory and message budgets.

This is a worthwhile upstream design, but it is a platform project. Implementing PDF review in core first provides a real use case from which to design the extension contract.

## 5. Recommended implementation sequence

1. **Open an upstream feature issue** describing “PDF review notes → batch send to agent,” explicitly distinguishing it from PDF-byte annotations. Link the existing PDF viewer and Markdown/diff annotation patterns.
2. Build a focused core proof of concept in `PdfViewer.tsx`:
   - capture text-layer selection;
   - resolve page number and convert DOM rectangles to normalized PDF coordinates;
   - render a non-interactive highlight overlay that tracks zoom/rotation;
   - persist one note in existing review state.
3. Add production anchoring:
   - PDF fingerprint/content hash;
   - text quote/prefix/suffix;
   - stale-note behavior after file changes;
   - multi-rect and area annotations;
   - keyboard accessibility and screen-reader labels.
4. Reuse the existing note composer/thread/resolve/batch-send UI and include page, quote, and optional screenshot in agent prompts.
5. Test local, Linux AppImage, remote runtime, SSH, tab hide/show, content reload, mixed page sizes, rotation, password/error cases, and large documents.
6. Only after review notes are solid, prototype native PDF.js highlight/free-text editing. Introduce an authorized atomic binary-write runtime API first; never overwrite via the text writer.
7. Separately propose viewer plugin extension points if a broader third-party document ecosystem is desired.

## Bottom line

Orca is unusually favorable for this feature because the complete app and current PDF.js viewer are public and actively developed. The installed Linux app already contains the necessary rendering engine; the missing part is product-level annotation state and persistence, not PDF rendering. The current plugin system is real but too narrow for custom file viewers, so the shortest credible path is a core Orca contribution implementing **non-destructive PDF review notes**, followed by optional PDF.js embedded annotation/save support.
