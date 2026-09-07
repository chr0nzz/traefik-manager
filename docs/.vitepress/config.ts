import { defineConfig } from 'vitepress'
import { tabsMarkdownPlugin } from 'vitepress-plugin-tabs'

export default defineConfig({
  title: 'Traefik Manager',
  description: 'Manage and monitor Traefik routes, middlewares, services, and providers through a clean web UI.',

  head: [
    ['link', { rel: 'icon', href: '/images/icon.png' }],
  ],

  vite: {
    server: {
      allowedHosts: ['tm-docs.xyzlab.dev'],
    },
  },

  markdown: {
    config(md) {
      md.use(tabsMarkdownPlugin)
    },
  },

  themeConfig: {
    logo: '/images/icon.png',
    siteTitle: 'Traefik Manager',

    nav: [
      { text: 'Overview', link: '/overview' },
      { text: 'FAQ', link: '/faq' },
      {
        text: 'Install',
        items: [
          { text: 'tm CLI (installer)', link: '/tm-cli' },
          { text: 'Docker', link: '/docker' },
          { text: 'Podman', link: '/podman' },
          { text: 'Linux (native)', link: '/linux' },
          { text: 'Unraid', link: '/unraid' },
        ],
      },
      {
        text: 'Reference',
        items: [
          { text: 'Environment Variables', link: '/env-vars' },
          { text: 'manager.yml', link: '/manager-yml' },
          { text: 'REST API', link: '/api' },
          { text: 'Agent API', link: '/api-agent' },
        ],
      },
      { text: 'Security', link: '/security' },
      {
        text: 'v1.13.3',
        items: [
          { text: 'v1.13.3', link: 'https://github.com/chr0nzz/traefik-manager/releases/tag/v1.13.3' },
          { text: 'All releases', link: 'https://github.com/chr0nzz/traefik-manager/releases' },
        ],
      },
    ],

    sidebar: [
      {
        text: 'Start here',
        items: [
          { text: 'Home', link: '/' },
          { text: 'Overview', link: '/overview' },
          { text: 'FAQ', link: '/faq' },
          { text: 'UI Examples', link: '/ui-examples' },
        ],
      },
      {
        text: 'Install',
        items: [
          { text: 'tm CLI (installer)', link: '/tm-cli' },
          { text: 'Docker', link: '/docker' },
          { text: 'Podman', link: '/podman' },
          { text: 'Linux (native)', link: '/linux' },
          { text: 'Unraid', link: '/unraid' },
          { text: 'Beta Channel', link: '/beta' },
        ],
      },
      {
        text: 'Traffic',
        items: [
          { text: 'Dashboard', link: '/tab-dashboard' },
          { text: 'Routes', link: '/tab-routes' },
          { text: 'Middlewares', link: '/tab-middlewares' },
          { text: 'Services', link: '/tab-services' },
          { text: 'Route Map', link: '/tab-routemap' },
        ],
      },
      {
        text: 'Observability',
        items: [
          { text: 'Logs', link: '/tab-logs' },
          { text: 'CrowdSec', link: '/tab-crowdsec' },
          { text: 'IP Geolocation', link: '/geoip' },
        ],
      },
      {
        text: 'Infrastructure',
        items: [
          { text: 'Certificates', link: '/tab-certs' },
          { text: 'TLS Options', link: '/tab-tls-options' },
          { text: 'Plugins', link: '/tab-plugins' },
          { text: 'Static Config Editor', link: '/static' },
          { text: 'Enabling Static Config', link: '/static-enable' },
        ],
      },
      {
        text: 'Providers',
        collapsed: true,
        items: [
          { text: 'Docker', link: '/tab-docker' },
          { text: 'Kubernetes', link: '/tab-kubernetes' },
          { text: 'Swarm', link: '/tab-swarm' },
          { text: 'Nomad', link: '/tab-nomad' },
          { text: 'ECS', link: '/tab-ecs' },
          { text: 'Consul Catalog', link: '/tab-consulcatalog' },
          { text: 'Redis', link: '/tab-redis' },
          { text: 'etcd', link: '/tab-etcd' },
          { text: 'Consul KV', link: '/tab-consul' },
          { text: 'ZooKeeper', link: '/tab-zookeeper' },
          { text: 'HTTP Provider', link: '/tab-http_provider' },
          { text: 'File (External)', link: '/tab-file_external' },
        ],
      },
      {
        text: 'Multi-Server',
        items: [
          { text: 'Agent', link: '/agent' },
          { text: 'Agent API Reference', link: '/api-agent' },
        ],
      },
      {
        text: 'Configuration',
        items: [
          { text: 'Environment Variables', link: '/env-vars' },
          { text: 'manager.yml', link: '/manager-yml' },
          { text: 'OIDC / SSO Login', link: '/oidc' },
          { text: 'Notification Webhooks', link: '/webhooks' },
          { text: 'Git Repository Backup', link: '/git-backup' },
        ],
      },
      {
        text: 'Security',
        items: [
          { text: 'Security', link: '/security' },
          { text: 'Traefik Hardening', link: '/hardening' },
          { text: 'Reset Password', link: '/reset-password' },
        ],
      },
      {
        text: 'Reference',
        items: [
          { text: 'REST API', link: '/api' },
          { text: 'Mobile App', link: '/mobile' },
          { text: 'Development', link: '/development' },
        ],
      },
    ],

    socialLinks: [
      { icon: 'github', link: 'https://github.com/chr0nzz/traefik-manager' },
    ],

    search: {
      provider: 'local',
    },
  },
})
