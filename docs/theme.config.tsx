import React, { useEffect, useState } from 'react'
import { DocsThemeConfig } from 'nextra-theme-docs'

function GithubStats() {
  const [stars, setStars] = useState<number | null>(null)
  const [forks, setForks] = useState<number | null>(null)

  useEffect(() => {
    fetch('https://api.github.com/repos/copinance/copinance-os')
      .then((res) => res.json())
      .then((data) => {
        setStars(data.stargazers_count || 0)
        setForks(data.forks_count || 0)
      })
      .catch(() => {
        setStars(0)
        setForks(0)
      })
  }, [])

  return (
    <>
      <a
        href="https://github.com/copinance/copinance-os/stargazers"
        target="_blank"
        rel="noopener noreferrer"
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: '0.25rem',
          marginRight: '1rem',
          textDecoration: 'none',
          color: 'inherit',
        }}
      >
        <svg
          width="16"
          height="16"
          viewBox="0 0 16 16"
          fill="currentColor"
          style={{ verticalAlign: 'middle' }}
        >
          <path d="M8 .25a.75.75 0 01.673.418l1.882 3.815 4.21.612a.75.75 0 01.416 1.279l-3.046 2.97.719 4.192a.75.75 0 01-1.088.791L8 12.347l-3.766 1.98a.75.75 0 01-1.088-.79l.72-4.194L.818 6.374a.75.75 0 01.416-1.28l4.21-.611L7.327.668A.75.75 0 018 .25z" />
        </svg>
        <span>{stars !== null ? stars : '-'}</span>
      </a>
      <a
        href="https://github.com/copinance/copinance-os/network/members"
        target="_blank"
        rel="noopener noreferrer"
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: '0.25rem',
          marginRight: '1rem',
          textDecoration: 'none',
          color: 'inherit',
        }}
      >
        <svg
          width="16"
          height="16"
          viewBox="0 0 16 16"
          fill="currentColor"
          style={{ verticalAlign: 'middle' }}
        >
          <path d="M5 3.25a.75.75 0 11-1.5 0 .75.75 0 011.5 0zm0 2.122a2.25 2.25 0 10-1.5 0v.878c0 .414.336.75.75.75h4.5A.75.75 0 0011 6.25v-.878a2.25 2.25 0 10-1.5 0v.878a.75.75 0 01-.75.75H6.5a.75.75 0 01-.75-.75v-.878zM3.25 7a.75.75 0 100-1.5.75.75 0 000 1.5zm9.5 0a.75.75 0 100-1.5.75.75 0 000 1.5z" />
          <path d="M5 8.25a.75.75 0 01.75-.75h4.5a.75.75 0 01.75.75v5.372a2.25 2.25 0 11-1.5 0V9h-3v4.622a2.25 2.25 0 11-1.5 0V8.25z" />
        </svg>
        <span>{forks !== null ? forks : '-'}</span>
      </a>
    </>
  )
}

const config: DocsThemeConfig = {
  logo: <span>Copinance OS</span>,
  project: {
    link: 'https://github.com/copinance/copinance-os',
  },
  navbar: {
    extraContent: <GithubStats />,
  },
  docsRepositoryBase: 'https://github.com/copinance/copinance-os/blob/main',
  footer: {
    text: 'Copyright © 2025 Copinance OS Contributors',
  },
  primaryHue: 210,
  primarySaturation: 50,
}

export default config

