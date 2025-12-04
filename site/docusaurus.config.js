// @ts-check

const organizationName = 'atlarge-research'
const projectName = 'opendt'

const lightCodeTheme = require('prism-react-renderer/themes/github')
const darkCodeTheme = require('prism-react-renderer/themes/dracula')

/** @type {import("@docusaurus/types").Config} */
const config = {
    title: 'OpenDT',
    tagline: 'Digital Twin for Datacenters',
    url: process.env.DOCUSAURUS_URL || `https://${organizationName}.github.io`,
    baseUrl: process.env.DOCUSAURUS_BASE_PATH || `/${projectName}/`,
    onBrokenLinks: 'throw',
    onBrokenMarkdownLinks: 'warn',
    favicon: 'img/favicon.ico',
    organizationName,
    projectName,

    i18n: {
        defaultLocale: 'en',
        locales: ['en'],
    },

    presets: [
        [
            'classic',
            /** @type {import("@docusaurus/preset-classic").Options} */
            ({
                docs: {
                    sidebarPath: require.resolve('./sidebars.js'),
                    editUrl: `https://github.com/${organizationName}/${projectName}/tree/master/site/`,
                },
                theme: {
                    customCss: require.resolve('./src/css/custom.css'),
                },
            }),
        ],
    ],

    themeConfig:
        /** @type {import("@docusaurus/preset-classic").ThemeConfig} */
        ({
            navbar: {
                title: 'OpenDT',
                logo: {
                    alt: 'OpenDT logo',
                    src: '/img/logo.svg',
                },
                items: [
                    {
                        type: 'doc',
                        docId: 'intro',
                        position: 'left',
                        label: 'Docs',
                    },
                    {
                        href: `https://github.com/${organizationName}/${projectName}`,
                        position: 'right',
                        className: 'header-github-link',
                        'aria-label': 'GitHub repository',
                    },
                ],
            },
            footer: {
                style: 'dark',
                links: [
                    {
                        title: 'Docs',
                        items: [
                            {
                                label: 'Getting Started',
                                to: '/docs/category/getting-started',
                            },
                            {
                                label: 'Concepts',
                                to: '/docs/category/concepts',
                            },
                            {
                                label: 'Configuration',
                                to: '/docs/category/configuration',
                            },
                            {
                                label: 'Services',
                                to: '/docs/category/services',
                            },
                        ],
                    },
                    {
                        title: 'More',
                        items: [
                            {
                                label: 'GitHub',
                                href: `https://github.com/${organizationName}/${projectName}`,
                            },
                            {
                                label: 'OpenDC',
                                href: 'https://opendc.org',
                            },
                        ],
                    },
                ],
                copyright: `Copyright © ${new Date().getFullYear()} AtLarge Research. Built with Docusaurus.`,
            },
            prism: {
                theme: lightCodeTheme,
                darkTheme: darkCodeTheme,
                additionalLanguages: ['bash', 'json', 'yaml'],
            },
        }),
}

module.exports = config
