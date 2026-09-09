{
  tag_name,
  published_at,
  release_url: .html_url,
  release_notes: (.body // ""),
  assets: [.assets[] | {
    name,
    size,
    sha256: (.digest | if . then ltrimstr("sha256:") else null end),
    url: .browser_download_url
  }]
}
