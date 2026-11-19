# OpenAI Codex desktop app: PDF review and annotation research

**Research date:** 2026-08-13 (sources include product reports through 2026-08-10)

## Bottom line

The desktop product **can preview PDFs and has a PDF annotation/comment affordance in some chat-linked artifact views**, but it is not an Acrobat-style PDF editor. Its annotations are feedback to the agent: the user identifies a passage or location, types an instruction, and sends it into the chat so Codex/ChatGPT can make another revision. I found no evidence that it writes standard PDF annotations into the PDF, exports an annotated PDF, or provides conventional highlight, ink, stamp, reply, author, or annotation-flattening tools.

The safest description is:

> The app has a built-in PDF/artifact previewer and an agent-feedback annotation layer. PDF annotation availability depends on how the PDF was opened and, in recent builds, may also depend on a remotely controlled batching feature. It should not be represented as a full PDF markup system.

OpenAI officially documents PDF previews and annotations on supported previews at a high level. It does **not** publish a detailed PDF-specific toolbar, annotation-type, persistence, or format-support specification. The most exact PDF workflow details currently come from user-filed issues in OpenAI's official `openai/codex` repository, so they are useful production evidence but not an OpenAI product guarantee.

## Product identity: “Codex app” versus the current desktop app

- OpenAI launched the standalone **Codex app for macOS** on 2026-02-02. Its first PDF-specific release note, app 26.204 on 2026-02-04, says “Added PDF preview in the review panel.” [Official changelog, 26.204](https://learn.chatgpt.com/docs/changelog#codex-2026-02-04-app)
- On 2026-07-09, OpenAI announced **“Codex joins the ChatGPT desktop app.”** Existing Codex app users retain their projects/settings/workflows and can make Codex the default view; on macOS they can keep the Codex icon. [Official changelog, 26.707](https://learn.chatgpt.com/docs/changelog#codex-2026-07-09-app)
- The old Codex app documentation URL, [`developers.openai.com/codex/app/`](https://developers.openai.com/codex/app/), now redirects to the unified [ChatGPT desktop app documentation](https://learn.chatgpt.com/docs/app). The current app quickstart explicitly tells the user to choose **ChatGPT or Codex**. Thus recent reports may say either “Codex,” “ChatGPT/Codex,” or “ChatGPT desktop,” although the selected agent/surface still matters.

## What the official documentation establishes

### Preview and review surfaces

The current official **Work with files** page says that the desktop app:

- previews generated **documents, presentations, spreadsheets, and PDF files alongside the chat**;
- can automatically open a generated file after a task when automatic previews are enabled;
- can render generated `.html` and `.htm` as interactive previews and switch between rendered and source views; and
- lets the user “use annotations to point at a specific part of a supported preview and request a focused revision.”

Source: [OpenAI, Work with files](https://learn.chatgpt.com/docs/artifacts-viewer).

The same page explains the purpose of annotations: they carry the selected area as context for a change request, so the user can refine an output without starting over. It explicitly says the workflow used for code, Markdown, and websites also works with **documents, spreadsheets, and presentations**. It gives examples such as highlighting a claim to ask for its source or marking a chart on a slide to request a clearer label. [Official annotation section](https://learn.chatgpt.com/docs/artifacts-viewer#refine-files-with-annotations)

There is a small but important documentation gap: that annotation paragraph does not expressly include “PDF” in its list, even though the paragraph above lists PDF as a preview type and says annotations work on a “supported preview.” Production reports below show a PDF annotation UI, but the official page does not provide a PDF-specific promise or procedure.

Official release history adds more context:

- **26.204, 2026-02-04:** PDF preview in the review panel. [Changelog](https://learn.chatgpt.com/docs/changelog#codex-2026-02-04-app)
- **26.205, 2026-02-05:** “Attach or drop any file type.” This means composer acceptance, not that every type has a rich preview or annotation UI. [Changelog](https://learn.chatgpt.com/docs/changelog#codex-2026-02-05-app)
- **26.410, 2026-04-12:** rich sidebar file-viewer previews for **images, PDFs, and Markdown**, plus a selected-text “Ask Codex” overlay. [Changelog](https://learn.chatgpt.com/docs/changelog#codex-2026-04-12-app)
- **26.415, 2026-04-16:** the artifact viewer can preview generated **PDFs, spreadsheets, documents, and presentations** in the sidebar before commit/share. [Changelog](https://learn.chatgpt.com/docs/changelog#codex-2026-04-16-app)
- **26.707, 2026-07-09:** edit Markdown and code in-app, use inline annotations, and ask Codex to revise selected content. [Changelog](https://learn.chatgpt.com/docs/changelog#codex-2026-07-09-app)

### Do not confuse file/PDF review with the Git code-review pane

The app also has a separate, officially documented **Git review pane**. `/review` reviews a base branch or uncommitted changes; findings and user comments attach to lines in a diff; the pane offers Unstaged, Staged, Commit, Branch, and Last turn scopes plus Git staging/revert operations. It requires a Git repository. That is code review, not PDF markup. [OpenAI, Code review](https://learn.chatgpt.com/docs/code-review?surface=app)

The historical release-note wording “PDF preview in the review panel” should therefore not be read as meaning that a PDF receives Git-style line comments. Current documentation describes PDFs in the artifact/file preview beside the chat.

## Exact PDF UI and workflow evidenced in production reports

The following details are from open issues in OpenAI's official repository, not from a formal UI specification.

### Where an annotatable PDF opens

A macOS report from 2026-06-08 describes two different views for the same local PDF:

1. When the assistant emits a local Markdown link such as `[example.pdf](/path/to/example.pdf)` and the user clicks it, the PDF opens in a **chat-linked viewer with an annotation/comment option**.
2. When the user opens the same PDF from the workspace **file window/sidebar**, it opens as a **read-only preview without the annotation option**.

The reporter found no visible way to change the sidebar preview into annotation mode. This is strong evidence that “the app can annotate PDFs” is too broad; the entry point matters. [openai/codex #26931](https://github.com/openai/codex/issues/26931)

A separate Sources-panel report says an attached PDF card shows a PDF icon, filename, original absolute path, and the text **“Attached to the conversation.”** Clicking it opens the right-hand viewer. In that build the “attachment” was actually dependent on the original local path; moving the file caused **“Couldn't load this preview.”** [openai/codex #33622](https://github.com/openai/codex/issues/33622)

### Adding and sending comments

A detailed 2026-08-08 report gives these reproduction steps for artifact annotation:

1. Open a document or PDF artifact in Codex Desktop.
2. Enter the annotation interface.
3. Select a **passage or location** and add an annotation.
4. Confirm the annotation.
5. The annotation is sent to the conversation and Codex begins a turn.

The report says older behavior stored multiple annotations as pending comments, allowed them to be reviewed together, and sent them once as a batch. In app 26.803.41515, each confirmed annotation instead began an agent turn immediately. The reporter says inspection of the production client showed `direct` and `saved` submission modes and an `annotationBatchingEnabled` value used by PDF, DOCX, spreadsheet, and slide preview components, controlled by feature gate `2581467225`. That reverse-engineering claim has not been confirmed by OpenAI, but it explains version/account-dependent behavior. [openai/codex #37554](https://github.com/openai/codex/issues/37554)

Therefore the workflow should be documented as **variable**:

- **Batched/saved mode (reported prior behavior):** collect pending annotations around the artifact, inspect the set, then deliberately send it to the chat as one turn.
- **Direct mode (reported in build 26.803.41515):** confirming each annotation immediately sends it to the conversation and starts work.

Do not promise that the user can batch, edit, or delete a complete pending set in every current build. OpenAI exposes no documented preference for these modes. A browser-only report found `Ctrl+Enter`/`Cmd+Enter` queues browser comments, but there is no reliable source showing that shortcut applies to PDFs. [Browser annotation issue #23871](https://github.com/openai/codex/issues/23871)

### Draft persistence

In app 26.623.70822 on macOS, a user reportedly added about 20 PDF review comments, reloaded/reopened the view, and lost every unsent draft; only the comment that had reached the thread remained visible. The issue asks for autosave or a warning and describes no recovery path. Until OpenAI documents or fixes this, users should send/copy important feedback before reload/navigation. [openai/codex #30761](https://github.com/openai/codex/issues/30761)

### Viewer controls and limitations observed in issue reports

These are version-specific observations, not official limits:

- The built-in PDF preview had **previous/next arrows only**, with no direct page-number field; reports say switching sidebar tabs resets the PDF to page 1. [#31704](https://github.com/openai/codex/issues/31704), [page-jump request #32717](https://github.com/openai/codex/issues/32717)
- A local workspace preview refused a 46.7 MB PDF and displayed **“File is too large to preview — 46.7 MB exceeds the 10.0 MB preview limit.”** No official document promises that 10 MB is a stable/current limit. [#26805](https://github.com/openai/codex/issues/26805)
- The PDF renderer did not follow the app's dark theme in a July Windows report; dark mode was requested, not documented as available. [#32498](https://github.com/openai/codex/issues/32498)
- Annotation text could become nearly invisible on a dark input background in one macOS build, confirming that the annotation UI includes a text input but also illustrating its instability. [#35569](https://github.com/openai/codex/issues/35569)
- Image preview exists, but a June feature request asked OpenAI to add region annotations to image previews “similar to” browser annotations. Image annotation should not be assumed merely because image preview is supported. [#28291](https://github.com/openai/codex/issues/28291)

## Supported formats: what can safely be claimed

| Capability | Safely supported by official documentation | Important qualification |
|---|---|---|
| Generated artifact preview in desktop app | Documents, presentations, spreadsheets, PDFs | Official docs name categories, not a complete extension/version/size matrix. |
| Sidebar rich file preview | Images, PDFs, Markdown | From app 26.410 release note. Preview does not imply annotation. |
| Interactive web preview | `.html`, `.htm` | Can switch rendered/source when HTML preview is available. |
| Officially described annotation/refinement | Code, Markdown, websites, documents, spreadsheets, presentations | PDF is not expressly repeated in this list; PDF annotation is evidenced by production issues. |
| PDF annotation/comment | Yes in at least the assistant-link/chat-linked artifact viewer in reported macOS/Windows builds | File-sidebar view may be read-only; batching can be feature-gated; no public annotation-type matrix. |
| General ChatGPT file uploads | Common text, spreadsheet, presentation, document formats; OpenAI specifically lists `XLSX`, `XLS`, `CSV`, `TSV`, `DOCX`, `PPTX`, `PDF`, `TXT` | This Help Center list is for ChatGPT file uploads, not a promise that every extension gets a Codex desktop rich preview. [Supported files](https://help.openai.com/en/articles/8983675-what-types-of-files-are-supported) |

The 26.205 phrase “any file type” should be interpreted as **attach/drop acceptance**, not universal parsing, rendering, or annotation.

## What “annotation” does and does not appear to mean

### Supported meaning

- A contextual instruction anchored to a selected passage, line, chart, UI region, or location.
- Sent into the conversation so the agent can understand focused feedback and revise the underlying/generated artifact.
- Potentially several comments collected into one agent request when batched mode is enabled.

### Not established

I found no official documentation or credible production evidence for:

- writing ISO PDF annotations into the PDF object model;
- saving an annotated copy of the original PDF;
- freehand ink, shapes, stamps, signatures, redaction, or measurement tools;
- durable highlight colors or an annotation sidebar with author/thread/reply states;
- exporting/importing FDF or XFDF;
- resolving PDF comments as a formal review workflow; or
- collaboration where other humans reply to annotations in the PDF.

The app should consequently be described as a **human-to-agent revision workflow**, not a general-purpose PDF annotation package.

## Codex PDF review versus ordinary ChatGPT PDF handling

These are related in the unified app but conceptually different.

### Codex/desktop artifact workflow

- Works around files in a local project/chat and generated outputs.
- Gives the human a rendered preview beside the agent transcript.
- Annotation is a way to provide precise revision instructions; the result is another agent turn and usually an edited/regenerated file.
- The viewer itself does not establish how much PDF text, charts, or embedded imagery the model can understand.

### ChatGPT upload/retrieval workflow

OpenAI's general file-upload documentation describes uploading a PDF to **summarize, compare, transform, or extract** content. It supports common document formats and states a 512 MB per-file upload limit and a 2-million-token limit for text/document files, with separate spreadsheet/image limits. Those are backend ChatGPT upload limits and should **not** be confused with the desktop previewer's reported 10 MB local preview ceiling. [OpenAI, File Uploads FAQ](https://help.openai.com/en/articles/8555545-file-uploads-faq)

For embedded PDF visuals, OpenAI's Help Center draws a plan/workflow distinction:

- **ChatGPT Enterprise** supports “Visual Retrieval” for PDFs attached in a prompt: it reads extracted text and embedded images, graphs, and diagrams.
- PDFs stored as **GPT Knowledge** or **Project Files** use text-only retrieval; PDFs uploaded by a user during a published-GPT interaction or within a Project conversation use visual retrieval.
- The Visual Retrieval FAQ says the feature is not supported for Free, Pro, Team, or Edu accounts; the general upload FAQ says all other plans and non-PDF document files use text-only retrieval and discard embedded images.

Sources: [Visual Retrieval with PDFs FAQ](https://help.openai.com/en/articles/10416312-visual-retrieval-with-pdfs-faq) and [File Uploads FAQ](https://help.openai.com/en/articles/8555545-file-uploads-faq).

Thus **ChatGPT PDF handling** primarily means model ingestion/retrieval and Q&A over an uploaded PDF. **Codex desktop PDF annotation** means visual review feedback that becomes an agent instruction. Neither implies the other: seeing a PDF in the Codex viewer is not proof of Enterprise visual retrieval, and ChatGPT being able to answer questions about an uploaded PDF is not proof of a graphical annotation UI.

## Documentation quality and confidence assessment

### Officially documented with high confidence

- PDF preview exists in the desktop app.
- Generated PDFs, documents, spreadsheets, and presentations can appear in the artifact viewer/sidebar.
- Supported previews can be annotated to request focused revisions.
- The standalone Codex experience was incorporated into the ChatGPT desktop app in July 2026.
- ChatGPT's upload/retrieval behavior and Enterprise-only PDF visual retrieval are documented separately.

### Production evidence, but not an official contract

- PDF annotations are available from a chat-linked/assistant-link viewer while the same sidebar-opened PDF can be read-only.
- PDF comments may be pending/batched or immediately sent depending on a feature gate/build.
- Unsent PDF comment drafts have been lost on reload.
- Page navigation, position retention, dark theme, local-path persistence, and preview-size behavior have had significant limitations.

### Unknown or undocumented

- Exact current toolbar labels/icons and supported annotation types.
- Whether every generated, uploaded, and existing local PDF gets the same annotation UI.
- Whether batched mode is currently enabled for a given account/platform.
- Annotation persistence guarantees and a recovery mechanism.
- A complete extension, encryption, font, accessibility, PDF-version, or maximum-size matrix for the desktop renderer.
- Whether PDF annotation coordinates/text selections are sent to the model as text, geometry, an image crop, or some combination.

## Recommended accurate wording

> In the ChatGPT desktop app's Codex workflow, generated PDFs can be previewed beside the chat. Some chat-linked PDF artifact views expose annotations: select a passage or location, add feedback, and send it to the agent for a focused revision. This is an agent-feedback layer, not standard PDF markup. Availability and comment batching have varied by viewer entry point, build, and feature flag, so verify the current app before relying on a long multi-comment review.

## Primary sources

1. [OpenAI: ChatGPT desktop app](https://learn.chatgpt.com/docs/app)
2. [OpenAI: Work with files / artifact viewer](https://learn.chatgpt.com/docs/artifacts-viewer)
3. [OpenAI: App/CLI changelog](https://learn.chatgpt.com/docs/changelog)
4. [OpenAI: Code review](https://learn.chatgpt.com/docs/code-review?surface=app)
5. [OpenAI Help: File Uploads FAQ](https://help.openai.com/en/articles/8555545-file-uploads-faq)
6. [OpenAI Help: supported file types](https://help.openai.com/en/articles/8983675-what-types-of-files-are-supported)
7. [OpenAI Help: Visual Retrieval with PDFs FAQ](https://help.openai.com/en/articles/10416312-visual-retrieval-with-pdfs-faq)
8. [openai/codex #26931: viewer entry-point inconsistency](https://github.com/openai/codex/issues/26931)
9. [openai/codex #30761: unsent PDF comments lost after reload](https://github.com/openai/codex/issues/30761)
10. [openai/codex #37554: direct versus saved/batched artifact annotations](https://github.com/openai/codex/issues/37554)
