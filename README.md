It's a recreation of USENET's functionality, but redone on top of the Reticulum Network, and running in a terminal thanks to Textual.

Each user is a "client" and a "server" - you post in a "newsgroup" (any arbitrary thing.with.this.format). Any other users on your same network can automatically see any "announced" servers, and they will automatically peer.

For remote servers, you can add IP addresses and build your peer networking that way.

Supports blacklisting of content you don't want to see using simple word filtering - anything you filter out will not be saved on your server by default, meaning any peers downstream of you will also not see the content you filtered out.

Good for filtering out spam, bad users, bad servers, etc.

Vibecoded as hell using Claude.
