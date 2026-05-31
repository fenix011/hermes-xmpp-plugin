# Changelog

All notable changes to this project will be documented in this file.

## [0.3.0] — First-class XMPP

### Added

- **XEP-0444 message reactions**: Lifecycle hooks send 👀/✅/❌ reactions when
  Hermes starts/finishes processing. Visible in XEP-0444-capable clients.
- **XEP-0461 threaded replies**: Inbound reply extraction and outbound reply
  sending preserve conversation threads.
- **XEP-0394 message markup**: Bold, code, and block-code spans are generated
  from Markdown-like syntax in Hermes responses.
- **XEP-0004 data forms for clarify**: Multi-choice clarify prompts are sent as
  data forms instead of plain text. Form responses are parsed and forwarded.
- **XEP-0050 ad-hoc commands**: Basic command-list registration on the bot JID
  for client-side command discovery.
- **XEP-0447 voice messages**: Voice audio is sent as Stateless File Sharing
  references after HTTP upload. Clients show file metadata before download.
- **XEP-0446 file metadata**: File sharing now includes metadata (name, size,
  media type) when supported.
- **Backward-compatible `send()` API**: Legacy parameters (`image_paths`,
  `voice_path`, `document_path`, `reply_to`, etc.) are still accepted.

### Fixed

- OMEMO class definitions no longer break import when `omemo` is not installed.
- Cross-test contamination resolved via `sys.modules` cache clearing.

### Deprecated

- Passing media through the generic `send()` method is deprecated. Use the
  dedicated `send_image()`, `send_voice()`, `send_document()` methods.

## [0.2.0] — Standalone plugin packaging

### Added

- Initial standalone packaging from upstream Hermes Agent PR code.
- 1:1 chat and MUC support.
- XEP-0085 typing indicators.
- XEP-0363 HTTP file upload.
- OMEMO end-to-end encryption (optional).
- `cron` and `send_message` standalone sender hook.
- Platform plugin registration.

## [0.1.0] — Unreleased

- Prototype explorations by Eric Lars Lee and Mibay.
