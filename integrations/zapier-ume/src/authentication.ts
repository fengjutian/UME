import type { ZObject, Bundle } from './types';

// Custom (API key) authentication for UME.
// The key is sent as "Authorization: Token <apiKey>" (matches UME's SDKs).
const test = (z: ZObject, _bundle: Bundle) => z.request({ url: '/v1/ping/', method: 'GET' });

export default {
	type: 'custom',
	test,
	fields: [
		{
			key: 'apiKey',
			label: 'UME API Key',
			// `password` so Zapier masks the key in the connection UI (it is a secret).
			type: 'password',
			required: true,
			helpText:
				'Your UME API key (starts with `m0-`). Create one at [app.ume.ai](https://app.ume.ai) → Settings → API Keys.',
		},
		{
			key: 'baseUrl',
			label: 'Base URL',
			type: 'string',
			required: false,
			default: 'https://api.ume.ai',
			helpText: 'Override only for self-hosted or non-default deployments.',
		},
	],
	// Shown on the connection label in the Zap editor. Uses the account email
	// from the /v1/ping/ test response so users with multiple UME connections
	// can tell them apart.
	connectionLabel: '{{user_email}}',
};
