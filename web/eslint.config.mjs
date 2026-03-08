import nextVitals from 'eslint-config-next/core-web-vitals';

const config = [
	...nextVitals,
	{
		rules: {
			'react-hooks/set-state-in-effect': 'off',
			'import/no-anonymous-default-export': 'off',
		},
	},
];

export default config;
