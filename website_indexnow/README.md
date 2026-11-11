# Odoo IndexNow SEO – Automatic URL Submission

IndexNow submission for standard Odoo 19 Website Builder pages (`website.page`).

## Features

- Independent key and configuration for every website/domain
- Root-level `/<key>.txt` key resource
- Automatic tracking for publish, edit, move, unpublish, restriction, de-indexing, and deletion
- Deduplicated asynchronous queue with batching and bounded retries
- Multilingual URL submission for enabled website languages
- Queue, immutable submission history, page status, dashboard, and manual submission wizard

## Setup

1. Install the module and open **Website → Configuration → Settings → IndexNow SEO**.
2. Select the website, configure its public HTTPS domain, and enable IndexNow.
3. Generate a key, save, then verify the public key file.
4. Submit all published pages once. Later changes are queued automatically.

A successful IndexNow response means that the provider received the URLs. It does not
guarantee crawling, ranking, or indexing.

## Scheduled actions

- **Process IndexNow queue** runs every five minutes.
- **Clean IndexNow records** runs daily and removes successful queue entries after 30 days and submission history after 90 days. Failed entries remain available.

## Multi-website behavior

Configuration, keys, queues, and history are isolated per website. Generic pages are
resolved separately for every website on which Odoo makes them available.

## Troubleshooting

- The website domain must be a public `http://` or `https://` URL.
- Localhost, loopback addresses, hostless values, and private IP addresses are rejected.
- A reverse proxy must forward the original host so Odoo can resolve the correct website.
- HTTP 400, 403, and 422 responses require configuration correction and are not retried automatically.
- HTTP 429, server errors, timeouts, and network failures use bounded backoff.

## Scope and limitations

Version 1 supports only standard Website Builder pages. Products, blogs, events,
forums, courses, jobs, portal records, quotations, and arbitrary URLs are excluded.
No feature promises immediate or guaranteed search-engine indexing.
