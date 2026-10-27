/** Copy shared by the public pages and their structured data. Keep claims in step with the code. */

export const CLONE_COMMAND = 'git clone https://github.com/bplogan/ffinn.git && cd ffinn && docker compose up'

export const AI_PROVIDERS = [
  'OpenAI',
  'Anthropic Claude',
  'Google Gemini',
  'Azure OpenAI',
  'GitHub Models',
  'Ollama',
  'Any OpenAI-compatible server',
] as const

export const FAQ = [
  {
    q: 'What is ffinn, in one sentence?',
    a: 'ffinn is a free, open-source foundation for business software (sign-in, teams, roles, billing and admin already built) with an AI agent that turns plain-English requests into reviewed pull requests, staging deploys and production releases.',
  },
  {
    q: 'Who is it for?',
    a: 'Businesses and product teams who want software shaped around how they work, without spending months rebuilding the basics first. You describe the feature; ffinn builds it on top of a foundation that is already production-minded.',
  },
  {
    q: 'Do I need a developer?',
    a: 'You need someone comfortable reviewing a pull request and running a deployment. The agent writes the code, but a person approves every change before it ships. That is a deliberate design choice, not a limitation.',
  },
  {
    q: 'Is it really free?',
    a: 'Yes. ffinn is MIT licensed with no paid tier and nothing held back. You pay only for your own hosting and for the AI usage on your own provider account.',
  },
  {
    q: 'Which AI models can I use?',
    a: 'OpenAI, Anthropic Claude, Google Gemini, Azure OpenAI, GitHub Models, Ollama for fully local models, or any OpenAI-compatible server. You bring your own key, and ffinn tests the connection before you save it.',
  },
  {
    q: 'Can the AI break my app?',
    a: 'The agent cannot write to protected core files such as auth, security, configuration and infrastructure. Every file it generates is checked against the architecture rules, sent back for a fix if it fails (up to three attempts), and then lands as a pull request you review. Production deploys wait for you.',
  },
  {
    q: 'Where do my code, data and keys live?',
    a: 'On infrastructure you control. The code is in your own GitHub repository, data stays in your PostgreSQL database, and AI provider keys and repository tokens are encrypted at rest in that database.',
  },
  {
    q: 'Which git hosts and clouds are supported?',
    a: 'The build agent works with GitHub and GitHub Actions today; GitLab and Azure DevOps are on the roadmap. ffinn runs anywhere Docker runs. The repository includes the AWS setup that runs ffinn.ca, and the portal can provision Azure, AWS, GCP and Oracle Cloud.',
  },
] as const
