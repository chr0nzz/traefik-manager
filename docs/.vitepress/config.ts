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
      { text: 'Home', link: '/' },
      { text: 'Guide', link: '/guide' },
      { text: 'Beta', link: '/beta' },
      { text: 'Security', link: '/security' },
      { text: 'API', link: '/api.html', target: '_self' },
      {
        text: 'v1.0.0-beta3.1',
        items: [
          { text: 'v1.0.0-beta3.1', link: 'https://github.com/chr0nzz/traefik-manager/releases/tag/v1.0.0-beta3.1' },
          { text: 'v1.0.0-beta3', link: 'https://github.com/chr0nzz/traefik-manager/releases/tag/v1.0.0-beta3' },
          { text: 'v1.0.0-beta2', link: 'https://github.com/chr0nzz/traefik-manager/releases/tag/v1.0.0-beta2' },
          { text: 'v1.0.0-beta1.1', link: 'https://github.com/chr0nzz/traefik-manager/releases/tag/v1.0.0-beta1.1' },
          { text: 'v1.0.0-beta1', link: 'https://github.com/chr0nzz/traefik-manager/releases/tag/v1.0.0-beta1' },
          { text: 'v0.12.0', link: 'https://github.com/chr0nzz/traefik-manager/releases/tag/v0.12.0' },
          { text: 'v0.11.0', link: 'https://github.com/chr0nzz/traefik-manager/releases/tag/v0.11.0' },
          { text: 'v0.10.4', link: 'https://github.com/chr0nzz/traefik-manager/releases/tag/v0.10.4' },
          { text: 'All releases', link: 'https://github.com/chr0nzz/traefik-manager/releases' },
        ],
      },
    ],

    sidebar: [
      { text: 'Home', link: '/' },
      { text: 'Guide', link: '/guide' },
      { text: 'Beta', link: '/beta' },
      { text: 'Mobile App', link: '/mobile' },
      { text: 'Security', link: '/security' },
      { text: 'API', link: '/api.html', target: '_self' },
      { text: 'UI Examples', link: '/ui-examples' },
      {
        text: 'Getting Started',
        collapsed: false,
        items: [
          { text: 'Traefik Stack', link: '/traefik-stack' },
          { text: 'Docker', link: '/docker' },
          { text: 'Podman', link: '/podman' },
          { text: 'Linux (native)', link: '/linux' },
          { text: 'Unraid', link: '/unraid' },
        ],
      },
      {
        text: 'Management',
        items: [
          { text: 'Routes', link: '/tab-routes' },
          { text: 'Middlewares', link: '/tab-middlewares' },
          { text: 'Services', link: '/tab-services' },
        ],
      },
      {
        text: 'Visualizations',
        items: [
          { text: 'Dashboard', link: '/tab-dashboard' },
          { text: 'Route Map', link: '/tab-routemap' },
        ],
      },
      {
        text: 'Monitoring',
        items: [
          { text: 'Certificates', link: '/tab-certs' },
          { text: 'Plugins', link: '/tab-plugins' },
          { text: 'Logs', link: '/tab-logs' },
        ],
      },
      {
        text: 'Providers',
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
        text: 'Configuration',
        items: [
          { text: 'Static Config Editor', link: '/static' },
          { text: 'manager.yml', link: '/manager-yml' },
          { text: 'Environment Variables', link: '/env-vars' },
          { text: 'OIDC / SSO Login', link: '/oidc' },
        ],
      },
      {
        text: 'Operations',
        items: [
          { text: 'Reset Password', link: '/reset-password' },
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
