# Slixmpp 1.15.0 XEP Plugin API Reference

Generated from slixmpp 1.15.0 source inspection for the Hermes XMPP platform plugin.

---

## XEP-0004: Data Forms

**Module:** `slixmpp.plugins.xep_0004.dataforms`
**Class:** `XEP_0004(BasePlugin)`
**Plugin name:** `'xep_0004'`
**Dependencies:** `{'xep_0030'}`
**Namespace:** `jabber:x:data`

### Plugin Methods

| Method | Signature | Description |
|--------|-----------|-------------|
| `make_form` | `(ftype='form', title='', instructions='') -> Form` | Create a new Form stanza with the given type, title, and instructions. |
| `handle_form` | `(message) -> None` | Internal handler; fires `message_xform` event. |
| `build_form` | `(xml) -> Form` | Build a Form stanza from existing XML. |

### Events

| Event Name | Trigger |
|------------|---------|
| `message_xform` | A data form is received in a message stanza (path: `message/form`). |

### Stanza Classes (`slixmpp.plugins.xep_0004.stanza`)

#### `Form(ElementBase)`

- **Namespace:** `jabber:x:data`
- **XML name:** `x`
- **plugin_attrib:** `'form'`
- **plugin_multi_attrib:** `'forms'`
- **Interfaces:** `instructions`, `reported`, `title`, `type`, `items`, `values`
- **Sub_interfaces:** `title`
- **form_types:** `{'cancel', 'form', 'result', 'submit'}`

**Key methods:**

| Method | Signature | Description |
|--------|-----------|-------------|
| `add_field` | `(var='', ftype=None, label='', desc='', required=False, value=None, options=None, **kwargs) -> FormField` | Add a field to the form. Returns the field. |
| `add_item` | `(values: dict) -> None` | Add a result item (for result forms). |
| `add_reported` | `(var, ftype=None, label='', desc='', **kwargs) -> FormField` | Add a reported field (column header for result forms). |
| `get_fields` | `(use_dict=False) -> dict` | Get all fields as a dict keyed by `var`. |
| `get_values` | `() -> dict` | Get all field values as a dict. |
| `set_values` | `(values: dict) -> None` | Set field values; auto-creates fields if missing. |
| `set_instructions` | `(instructions) -> None` | Set instructions text (string or list). |
| `cancel` | `() -> None` | Set form type to 'cancel'. |
| `reply` | `() -> None` | Flip form type: form→submit, submit→result. |
| `merge` | `(other) -> Form` | Merge with another form or dict; returns new Form. |

#### `FormField(ElementBase)`

- **Namespace:** `jabber:x:data`
- **XML name:** `field`
- **plugin_attrib:** `'field'`
- **plugin_multi_attrib:** `'fields'`
- **Interfaces:** `answer`, `desc`, `required`, `value`, `label`, `type`, `var`
- **field_types:** `{'boolean', 'fixed', 'hidden', 'jid-multi', 'jid-single', 'list-multi', 'list-single', 'text-multi', 'text-private', 'text-single'}`

**Key methods:**

| Method | Signature | Description |
|--------|-----------|-------------|
| `add_option` | `(label='', value='') -> None` | Add an option (for list-* types). |
| `get_value` | `(convert=True, convert_list=False) -> Any` | Get field value; auto-converts booleans, multi-values. |
| `set_value` | `(value) -> None` | Set field value; handles bool, str, list types. |
| `set_options` | `(options) -> None` | Set multiple options at once. |
| `set_required` | `(required: bool) -> None` | Set whether field is required. |

#### `FieldOption(ElementBase)`

- **Namespace:** `jabber:x:data`
- **XML name:** `option`
- **plugin_attrib:** `'option'`
- **Interfaces:** `label`, `value`

### Example Usage

```python
# Create a data form
form = xmpp['xep_0004'].make_form(ftype='form', title='Survey', instructions='Please fill out')
form.add_field(var='name', ftype='text-single', label='Your Name', required=True)
form.add_field(var='color', ftype='list-single', label='Favorite Color',
               options=[{'label': 'Red', 'value': 'red'}, {'label': 'Blue', 'value': 'blue'}])

# Access received form fields
form = msg['form']
values = form['values']  # dict of var->value
name = form.get_fields()['name']['value']

# Merge with a dict of answers
submitted = form.merge({'name': 'Alice', 'color': 'red'})
```

---

## XEP-0050: Ad-Hoc Commands

**Module:** `slixmpp.plugins.xep_0050.adhoc`
**Class:** `XEP_0050(BasePlugin)`
**Plugin name:** `'xep_0050'`
**Dependencies:** `{'xep_0030', 'xep_0004'}`
**Namespace:** `http://jabber.org/protocol/commands`
**Default config:** `{'session_db': None}`

### Type Aliases

- `SessionDict = dict[str, Any]`
- `HandlerType = Callable[[Iq, SessionDict], Awaitable[SessionDict] | SessionDict]`
- `TimeoutHandlerType = Callable[[SessionDict], Awaitable[None]]`
- `CommandType = tuple[str, HandlerType | None, TimeoutHandlerType | None, float]`

### Server-Side (Command Provider) Methods

| Method | Signature | Description |
|--------|-----------|-------------|
| `add_command` | `(jid=None, node=None, name='', handler=None, *, timeout=0, timeout_handler=None) -> None` | Register a new ad-hoc command. Handler receives `(Iq, SessionDict)` and returns `SessionDict`. |
| `new_session` | `() -> str` | Generate a new unique session ID. |
| `set_backend` | `(db) -> None` | Replace default session dict with external storage. |
| `prep_handlers` | `(handlers, **kwargs) -> None` | Hook for backend services to prepare handlers (no-op by default). |

### Client-Side (Command User) Methods

| Method | Signature | Description |
|--------|-----------|-------------|
| `get_commands` | `(jid, **kwargs) -> Future` | Query a JID for available commands (uses disco items). |
| `send_command` | `(jid, node, ifrom=None, action='execute', payload=None, sessionid=None, flow=False, **kwargs) -> Future` | Send a raw command IQ; if `flow=True`, processes result via session workflow. |
| `start_command` | `(jid, node, session, ifrom=None) -> None` | Initiate a command with a session dict containing `next` and `error` handlers. |
| `continue_command` | `(session, direction='next') -> None` | Continue a multi-step command (next/prev). |
| `cancel_command` | `(session) -> None` | Cancel a running command session. |
| `complete_command` | `(session) -> None` | Complete (finish) a command workflow. |
| `terminate_command` | `(session) -> None` | Delete session data after command completion or error. |

### Events

| Event Name | Trigger |
|------------|---------|
| `command` | Any ad-hoc command IQ received. |
| `command_execute` | Command with `action="execute"`. |
| `command_next` | Command with `action="next"`. |
| `command_complete` | Command with `action="complete"`. |
| `command_cancel` | Command with `action="cancel"`. |

### Session Dict Structure

When a handler is called, the `SessionDict` contains:

```python
{
    'id': str,              # Session ID
    'from': JID,            # Sender JID
    'to': JID,              # Recipient JID
    'node': str,            # Command node
    'payload': list|object, # Attached payload (e.g. Form)
    'interfaces': set,      # Payload plugin_attrib values
    'payload_classes': set, # Payload class types
    'notes': list|None,     # List of (type, text) tuples
    'has_next': bool,       # Whether there's a next step
    'allow_complete': bool, # Whether 'complete' action is allowed
    'allow_prev': bool,     # Whether 'prev' action is allowed
    'past': list,           # Previous step handlers
    'next': callable|None,  # Handler for next step
    'prev': callable|None,  # Handler for prev step
    'cancel': callable|None,# Handler for cancel
}
```

### Stanza Classes (`slixmpp.plugins.xep_0050.stanza`)

#### `Command(ElementBase)`

- **Namespace:** `http://jabber.org/protocol/commands`
- **XML name:** `command`
- **plugin_attrib:** `'command'`
- **Interfaces:** `action`, `sessionid`, `node`, `status`, `actions`, `notes`
- **actions:** `{'cancel', 'complete', 'execute', 'next', 'prev'}`
- **statuses:** `{'canceled', 'completed', 'executing'}`
- **next_actions:** `{'prev', 'next', 'complete'}`

**Key methods:**

| Method | Signature | Description |
|--------|-----------|-------------|
| `set_actions` | `(values: list) -> None` | Set allowable next actions (prev/next/complete). |
| `get_actions` | `() -> set` | Get allowable next actions. |
| `add_note` | `(msg='', ntype='info') -> None` | Add a note annotation (type: info/warning/error). |
| `set_notes` | `(notes: list[tuple]) -> None` | Set multiple notes at once. |
| `get_notes` | `() -> list[tuple]` | Get list of (type, text) note tuples. |

### Example Usage

```python
# Server-side: register a command
async def my_handler(iq, session):
    form = xmpp['xep_0004'].make_form(ftype='form', title='My Command')
    form.add_field(var='input', ftype='text-single', label='Enter value')
    session['payload'] = form
    session['has_next'] = True
    session['next'] = my_next_step
    return session

xmpp['xep_0050'].add_command(node='mycmd', name='My Command', handler=my_handler)

# Client-side: start a command
session = {'next': handle_result, 'error': handle_error}
xmpp['xep_0050'].start_command('bot@example.com', 'mycmd', session)

# Client-side: send a raw command
result = await xmpp['xep_0050'].send_command(
    jid='bot@example.com', node='mycmd', action='execute'
)
```

---

## XEP-0394: Message Markup

**Module:** `slixmpp.plugins.xep_0394.markup`
**Class:** `XEP_0394(BasePlugin)`
**Plugin name:** `'xep_0394'`
**Dependencies:** `{'xep_0030', 'xep_0071'}`
**Namespace:** `urn:xmpp:markup:0`

### Plugin Methods

| Method | Signature | Description |
|--------|-----------|-------------|
| `to_plain_text` | `(body: str, markup_elem: Markup) -> str` | Extract plain text from a body with markup, stripping all markup annotations. |
| `to_xhtml_im` | `(body: str, markup_elem: Markup) -> XHTML_IM` | Convert a body with markup annotations to XHTML-IM format. |
| `_split_first_level` | `(body, markup_elem) -> list` | (Static) Split body into chunks interleaved with Start/End markers for markup elements. |

### Events

None registered by this plugin. Markup is accessed via `msg['markup']` on received messages.

### Stanza Classes (`slixmpp.plugins.xep_0394.stanza`)

#### `Markup(ElementBase)`

- **Namespace:** `urn:xmpp:markup:0`
- **XML name:** `markup`
- **plugin_attrib:** `'markup'`
- Contains iterable sub-stanzas: `Span`, `BlockCode`, `List`, `BlockQuote`

#### `_FirstLevel(ElementBase)` — Base class for top-level markup elements

- **Interfaces:** `start`, `end` (integer character indices into the body text)

#### `Span(_FirstLevel)`

- **XML name:** `span`
- **plugin_attrib:** `'span'`
- **plugin_multi_attrib:** `'spans'`
- **Interfaces:** `start`, `end`, `types`
- **Valid types:** `'emphasis'`, `'code'`, `'deleted'`
- Types are represented as child elements (e.g. `<emphasis/>`, `<code/>`, `<deleted/>`).

#### `BlockCode(_FirstLevel)`

- **XML name:** `bcode`
- **plugin_attrib:** `'bcode'`
- **plugin_multi_attrib:** `'bcodes'`
- **Interfaces:** `start`, `end`

#### `List(_FirstLevel)`

- **XML name:** `list`
- **plugin_attrib:** `'list'`
- **plugin_multi_attrib:** `'lists'`
- **Interfaces:** `start`, `end`, `li`
- Contains iterable `Li` sub-stanzas.

#### `Li(ElementBase)`

- **Namespace:** `urn:xmpp:markup:0`
- **XML name:** `li`
- **plugin_attrib:** `'li'`
- **plugin_multi_attrib:** `'lis'`
- **Interfaces:** `start` (integer character index)

#### `BlockQuote(_FirstLevel)`

- **XML name:** `bquote`
- **plugin_attrib:** `'bquote'`
- **plugin_multi_attrib:** `'bquotes'`
- **Interfaces:** `start`, `end`

#### Span type sub-elements

- `EmphasisType` — `<emphasis/>`
- `CodeType` — `<code/>`
- `DeletedType` — `<deleted/>`

### Example Usage

```python
# Read markup from a received message
markup = msg['markup']
for span in markup['spans']:
    print(f'Span [{span["start"]}:{span["end"]}] types={span["types"]}')
for bcode in markup['bcodes']:
    print(f'BlockCode [{bcode["start"]}:{bcode["end"]}]')

# Convert to XHTML-IM
xhtml = xmpp['xep_0394'].to_xhtml_im(msg['body'], msg['markup'])

# Manually construct markup on an outgoing message
from slixmpp.plugins.xep_0394.stanza import Markup, Span, BlockCode, List, Li, BlockQuote
markup = Markup()
span = Span()
span['start'] = 0
span['end'] = 5
span['types'] = ['emphasis']
markup.append(span)
msg['markup'] = markup
```

---

## XEP-0444: Message Reactions

**Module:** `slixmpp.plugins.xep_0444.reactions`
**Class:** `XEP_0444(BasePlugin)`
**Plugin name:** `'xep_0444'`
**Dependencies:** `{'xep_0030', 'xep_0334'}`
**Namespace:** `urn:xmpp:reactions:0`

### Plugin Methods

| Method | Signature | Description |
|--------|-----------|-------------|
| `send_reactions` | `(to: JID, to_id: str, reactions: Iterable[str], *, store=True) -> None` | Send a message with reactions to a specific message ID. `store=True` adds a store hint (XEP-0334). |
| `set_reactions` | `(message: Message, to_id: str, reactions: Iterable[str]) -> None` | (Static) Add reactions to an existing Message object without sending it. |

### Events

| Event Name | Trigger |
|------------|---------|
| `reactions` | A message with a `<reactions>` element is received. The `message` stanza is passed. |

### Stanza Classes (`slixmpp.plugins.xep_0444.stanza`)

#### `Reactions(ElementBase)`

- **Namespace:** `urn:xmpp:reactions:0`
- **XML name:** `reactions`
- **plugin_attrib:** `'reactions'`
- **Interfaces:** `id`, `values`
- Contains iterable `Reaction` sub-stanzas.

**Key methods:**

| Method | Signature | Description |
|--------|-----------|-------------|
| `get_values` | `(*, all_chars=False) -> set[str]` | Get all reaction emoji values as a set. Validates emoji unless `all_chars=True`. |
| `set_values` | `(values: Iterable[str], *, all_chars=False) -> None` | Replace all reactions with the given values. |

#### `Reaction(ElementBase)`

- **Namespace:** `urn:xmpp:reactions:0`
- **XML name:** `reaction`
- **Interfaces:** `value`

**Key methods:**

| Method | Signature | Description |
|--------|-----------|-------------|
| `get_value` | `() -> str` | Get the emoji string. |
| `set_value` | `(value: str, *, all_chars=False) -> None` | Set the emoji. Raises `ValueError` if not valid emoji (unless `all_chars=True`). Requires `python-emoji` library for validation; without it, all values are accepted. |

### Example Usage

```python
# Send reactions
xmpp['xep_0444'].send_reactions(
    to=JID('user@example.com'),
    to_id='msg-id-123',
    reactions=['👍', '❤️']
)

# Add reactions to a message before sending
msg = xmpp.make_message(mto='user@example.com')
xmpp['xep_0444'].set_reactions(msg, 'msg-id-123', ['👋'])
msg.send()

# Handle incoming reactions
def on_reactions(msg):
    reaction_id = msg['reactions']['id']
    emojis = msg['reactions']['values']  # set of str
    print(f'Reactions to {reaction_id}: {emojis}')

xmpp.add_event_handler('reactions', on_reactions)
```

---

## XEP-0461: Message Replies

**Module:** `slixmpp.plugins.xep_0461.reply`
**Class:** `XEP_0461(BasePlugin)`
**Plugin name:** `'xep_0461'`
**Dependencies:** `{'xep_0030', 'xep_0428'}`  (XEP-0428 = Fallback Indication)
**Namespace:** `urn:xmpp:reply:0`

### Plugin Methods

| Method | Signature | Description |
|--------|-----------|-------------|
| `make_reply` | `(reply_to: JidStr, reply_id: str, fallback: str|None=None, quoted_nick: str|None=None, **msg_kwargs) -> Message` | Create a reply Message stanza. `msg_kwargs` are passed to `make_message()` (requires `mto`, `mbody`). If `fallback` is provided, quoted fallback text is prepended to body with XEP-0428 fallback markers. |
| `send_reply` | `(reply_to: JidStr, reply_id: str, fallback: str|None=None, quoted_nick: str|None=None, **msg_kwargs) -> None` | Create and immediately send a reply message. |

### Events

| Event Name | Trigger |
|------------|---------|
| `message_reply` | A message with a `<reply>` element is received. The full `Message` stanza is passed. |

### Stanza Classes (`slixmpp.plugins.xep_0461.stanza`)

#### `Reply(ElementBase)`

- **Namespace:** `urn:xmpp:reply:0`
- **XML name:** `reply`
- **plugin_attrib:** `'reply'`
- **Interfaces:** `id`, `to`

**Key methods:**

| Method | Signature | Description |
|--------|-----------|-------------|
| `add_quoted_fallback` | `(fallback: str, nickname: str|None=None) -> None` | Prepend quoted fallback text to the parent message body and add XEP-0428 `<fallback>` markers. Format: `> Nick:\n> text\n`. |
| `get_fallback_body` | `() -> str` | Extract the fallback body text from the parent message using fallback markers. |
| `strip_fallback_content` | `() -> str` | Remove fallback content from the parent message body; returns the body without fallback. |

### Example Usage

```python
# Send a reply with fallback
xmpp['xep_0461'].send_reply(
    reply_to='user@example.com/resource',
    reply_id='original-msg-id',
    fallback='Original message text',
    quoted_nick='Alice',
    mto='user@example.com',
    mbody='I agree!'
)

# Make a reply without sending
msg = xmpp['xep_0461'].make_reply(
    reply_to='user@example.com/resource',
    reply_id='original-msg-id',
    mto='user@example.com',
    mbody='Response text'
)
msg.send()

# Handle incoming replies
def on_reply(msg):
    reply_to_jid = msg['reply']['to']
    reply_to_id = msg['reply']['id']
    real_body = msg['reply'].strip_fallback_content()
    print(f'Reply to {reply_to_id} from {reply_to_jid}: {real_body}')

xmpp.add_event_handler('message_reply', on_reply)

# Manually construct reply on a message
msg = xmpp.make_message(mto='user@example.com', mbody='My reply')
msg['reply']['to'] = 'sender@example.com/resource'
msg['reply']['id'] = 'original-msg-id'
msg['reply'].add_quoted_fallback('Original text', 'Bob')
msg.send()
```

---

## XEP-0446: File Metadata Element

**Module:** `slixmpp.plugins.xep_0446.file_metadata`
**Class:** `XEP_0446(BasePlugin)`
**Plugin name:** `'xep_0446'`
**Dependencies:** `{'xep_0300', 'xep_0264'}` (Hashes, Bits of Binary for thumbnails)
**Namespace:** `urn:xmpp:file:metadata:0`

### Plugin Methods

None beyond `plugin_init` which calls `stanza.register_plugins()`.

This plugin is primarily a stanza provider — it registers the `File` element for use by other plugins (especially XEP-0447).

### Stanza Classes (`slixmpp.plugins.xep_0446.stanza`)

#### `File(ElementBase)`

- **Namespace:** `urn:xmpp:file:metadata:0`
- **XML name:** `file`
- **plugin_attrib:** `'file'`
- **Interfaces/Sub_interfaces:** `media-type`, `name`, `date`, `size`, `desc`, `width`, `height`, `length`
- Registered sub-stanzas: `Hash` (from XEP-0300), `Thumbnail` (from XEP-0264)

**Key property methods:**

| Interface | Getter Type | Setter Type | Notes |
|-----------|------------|------------|-------|
| `media-type` | `str` | `str` | MIME type (e.g. `'image/png'`) |
| `name` | `str` | `str` | Filename |
| `date` | `datetime|None` | `datetime` | Parsed via XEP-0082 |
| `size` | `int|None` | `int` | File size in bytes (must be positive) |
| `desc` | `str` | `str` | Human-readable description |
| `width` | `int|None` | `int` | Image/video width (must be positive) |
| `height` | `int|None` | `int` | Image/video height (must be positive) |
| `length` | `int|None` | `int` | Audio/video duration in seconds (must be positive) |

Setters for `width`, `height`, `length`, `size` raise `ValueError` for non-positive values.

### Example Usage

```python
from slixmpp.plugins.xep_0446.stanza import File

# Create file metadata
file_elem = File()
file_elem['name'] = 'photo.jpg'
file_elem['media-type'] = 'image/jpeg'
file_elem['size'] = 61440
file_elem['width'] = 800
file_elem['height'] = 600
file_elem['desc'] = 'A nice photo'

# Attach a hash
from slixmpp.plugins.xep_0300 import Hash
h = Hash()
h['algo'] = 'sha-256'
h['value'] = 'base64hashvalue'
file_elem.append(h)
```

---

## XEP-0447: Stateless File Sharing

**Module:** `slixmpp.plugins.xep_0447.sfs`
**Class:** `XEP_0447(BasePlugin)`
**Plugin name:** `'xep_0447'`
**Dependencies:** `{'xep_0300', 'xep_0446'}`
**Namespace:** `urn:xmpp:sfs:0`

**Important:** The plugin docstring states: "Only support outgoing SFS, incoming is not handled at all."

### Plugin Methods

| Method | Signature | Description |
|--------|-----------|-------------|
| `get_sfs` | `(path: Path, uris: Iterable[str]|None=None, media_type: str|None=None, desc: str|None=None, disposition: Literal['inline','attachment']|None=None) -> StatelessFileSharing` | Create a complete SFS element from a local file path. Auto-fills `name`, `size`, `date`, and computes hash via XEP-0300. |

### Events

None. Incoming SFS messages are not processed by this plugin; access via `msg['sfs']` on received messages.

### Stanza Classes (`slixmpp.plugins.xep_0447.stanza`)

#### `StatelessFileSharing(ElementBase)`

- **Namespace:** `urn:xmpp:sfs:0`
- **XML name:** `file-sharing`
- **plugin_attrib:** `'sfs'`
- **Interfaces:** `disposition`
- Registered sub-stanzas: `Sources`, `File` (from XEP-0446)

#### `Sources(ElementBase)`

- **Namespace:** `urn:xmpp:sfs:0`
- **XML name:** `sources`
- **plugin_attrib:** `'sources'`
- Contains iterable `UrlData` sub-stanzas.

#### `UrlData(ElementBase)`

- **Namespace:** `http://jabber.org/protocol/url-data`
- **XML name:** `url-data`
- **plugin_attrib:** `'url-data'`
- **Interfaces:** `target` — the URL string for the file source.

### Example Usage

```python
from pathlib import Path

# Create SFS from a local file
sfs = xmpp['xep_0447'].get_sfs(
    path=Path('/tmp/document.pdf'),
    uris=['https://example.com/files/document.pdf'],
    media_type='application/pdf',
    desc='Project documentation',
    disposition='attachment'
)

# Attach SFS to a message and send
msg = xmpp.make_message(mto='user@example.com')
msg.append(sfs)
msg['body'] = 'Here is the file'
msg.send()

# Read SFS from an incoming message
sfs = msg['sfs']
disposition = sfs['disposition']
file_name = sfs['file']['name']
file_size = sfs['file']['size']
for source in sfs['sources']['substanzas']:
    if source.plugin_attrib == 'url-data':
        url = source['target']

# Manually construct SFS without local file
from slixmpp.plugins.xep_0447.stanza import StatelessFileSharing, Sources, UrlData
sfs = StatelessFileSharing()
sfs['disposition'] = 'inline'
file = sfs['file']
file['name'] = 'photo.jpg'
file['size'] = 61440
file['media-type'] = 'image/jpeg'
url = UrlData()
url['target'] = 'https://example.com/photo.jpg'
sfs['sources'].append(url)
```

---

## Summary of Key API Patterns for Hermes Integration

### Sending Patterns

1. **Reactions** (`xep_0444`): `xmpp['xep_0444'].send_reactions(to, msg_id, ['👍'])` — simplest API; one call.
2. **Replies** (`xep_0461`): `xmpp['xep_0461'].send_reply(reply_to, reply_id, fallback_text, nick, mto=..., mbody=...)` — builds + sends with fallback.
3. **File Sharing** (`xep_0447`): `xmpp['xep_0447'].get_sfs(path, uris)` → append to message → send.
4. **Ad-Hoc Commands** (`xep_0050`): `xmpp['xep_0050'].add_command(node, name, handler)` for server; `start_command()` / `send_command()` for client.
5. **Data Forms** (`xep_0004`): `xmpp['xep_0004'].make_form()` → `add_field()` → attach to IQ/message.
6. **Markup** (`xep_0394`): Build `Markup` stanza with `Span`/`BlockCode`/`List`/`BlockQuote` children, set `start`/`end` indices.

### Receiving Patterns

1. **Reactions**: Listen for `'reactions'` event → `msg['reactions']['id']` and `msg['reactions']['values']`.
2. **Replies**: Listen for `'message_reply'` event → `msg['reply']['id']`, `msg['reply']['to']`, `msg['reply'].strip_fallback_content()`.
3. **Data Forms**: Listen for `'message_xform'` event → `msg['form']['values']`.
4. **Ad-Hoc Commands**: Listen for `'command_execute'` / `'command_next'` / etc. events.
5. **SFS/Markup**: No events — access via `msg['sfs']` / `msg['markup']` on any received message.

### Accessing Stanzas on Messages

All these plugins register stanza plugins on `Message` (or `Iq` for commands):

- `msg['form']` — XEP-0004 Data Form
- `msg['command']` — XEP-0050 Command (on Iq)
- `msg['markup']` — XEP-0394 Markup
- `msg['reactions']` — XEP-0444 Reactions
- `msg['reply']` — XEP-0461 Reply
- `msg['sfs']` — XEP-0447 Stateless File Sharing
- `msg['file']` — XEP-0446 File Metadata (usually accessed via `msg['sfs']['file']`)
