# If this is ever hosted

Allan's answer to "are users uploading scans to your server acceptable" was: yes,
**as long as it is intuitive** — "users are double the dumb we assume". That is a
usability answer, and it has consequences for privacy that are worth writing down
before any of it is built, because they are hard to reverse once people have
uploaded things.

## What local-only gets you today

The current shape is a localhost server plus a browser page. Scans are read from a
folder the user picks, transcriptions are written next to them, and nothing leaves
the machine. There is no account, no bucket, no retention policy, and no breach to
have. That is worth something in a corpus of civil records about named living
people's ancestors — and, for the jus sanguinis use, about documents that are being
prepared as legal evidence.

## What hosting would add, and cost

**Added:** no install, no Python, no "which venv"; a shared index, so two people
researching the same ship see each other's corrections; indexing on a machine that
is not the user's laptop, which matters when a folder takes hours.

**Cost, in order of how much it should worry us:**

1. **The uploads are personal records.** A passenger manifest names a person, their
   age, nationality, occupation and where they sailed from. Users will upload family
   documents alongside them — passports, certificates — because the interface will
   not stop them. Anything accepted must be treated as personal data from the moment
   it is received, not from the moment it is parsed.
2. **Deletion has to be real.** "Delete" must remove the scan, the rendered page
   cache, the transcription, and the search index entry. A cache that outlives the
   delete button is the failure people will not forgive.
3. **Retention must be short and stated on the upload screen**, in the same words
   the user is thinking in — not in a linked policy.
4. **Cost of indexing is real CPU.** At ~4 s/page, a thousand-page upload is over an
   hour of a core. Hosted means paying for that, and means queueing, which means the
   interface has to be honest that work is pending.
5. **Sharing is the feature people will ask for next**, and it is the one that turns
   a private upload into a leak if the default is wrong. Default private.

## What "intuitive" has to mean here

Given the user Allan describes, the interface may not ask anyone to understand any
of the above. Concretely:

* one screen, one action, and the estimate in hours, not a progress percentage;
* the delete button next to the upload, not in a settings page;
* say what happens to the file in one sentence, at the moment it is chosen;
* never silently keep a copy for "improving the model" — that is not on the table
  while the engine is a local open-weight model, and it should not become so by
  accident.

## Recommendation

Keep local-only as the shipped default, and treat hosting as a separate deployment
of the same code with an explicit privacy page. The engine is already local and
open-weight, so nothing about the transcription needs a server; only convenience
does. That is a good trade to make late rather than early.
