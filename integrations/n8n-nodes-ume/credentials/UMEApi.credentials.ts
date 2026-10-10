import {
	IAuthenticateGeneric,
	Icon,
	ICredentialTestRequest,
	ICredentialType,
	INodeProperties,
} from 'n8n-workflow';

export class UMEApi implements ICredentialType {
	name = 'umeApi';

	displayName = 'UME API';

	icon: Icon = { light: 'file:ume.svg', dark: 'file:ume.svg' };

	documentationUrl = 'https://docs.ume.ai/platform/quickstart';

	properties: INodeProperties[] = [
		{
			displayName: 'API Key',
			name: 'apiKey',
			type: 'string',
			typeOptions: { password: true },
			default: '',
			required: true,
			description: 'Your UME API key (starts with "m0-"). Create one at app.ume.ai → Settings → API Keys.',
		},
		{
			displayName: 'Base URL',
			name: 'baseUrl',
			type: 'string',
			default: 'https://api.ume.ai',
			description: 'UME API base URL. Override only for self-hosted or non-default deployments.',
		},
	];

	// Injects "Authorization: Token <apiKey>" on every request, matching the
	// scheme used by UME's official SDKs (Authorization: Token m0-...).
	authenticate: IAuthenticateGeneric = {
		type: 'generic',
		properties: {
			headers: {
				Authorization: '=Token {{$credentials.apiKey}}',
			},
		},
	};

	// Cheap authenticated GET; validates the key when the user clicks "Test".
	test: ICredentialTestRequest = {
		request: {
			baseURL: '={{$credentials.baseUrl}}',
			url: '/v1/ping/',
			method: 'GET',
		},
	};
}
