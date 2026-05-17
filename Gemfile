source "https://rubygems.org"

# GitHub Pages gem — garante compatibilidade com o ambiente do GitHub Pages
gem "github-pages", group: :jekyll_plugins

# Plugins adicionais
# NB: jekyll-sitemap intentionally NOT listed — we ship hand-written
# sitemap.xml / sitemap-news.xml with news+image annotations the plugin
# can't emit. Letting jekyll-sitemap also walk the 16k+ tag pages
# pushed builds past the CI timeout.
group :jekyll_plugins do
  gem "jekyll-seo-tag"
  gem "jekyll-feed"
  gem "jekyll-paginate"
end

# Dependências Windows (ignorado em outros SOs)
platforms :mingw, :x64_mingw, :mswin, :jruby do
  gem "tzinfo", ">= 1", "< 3"
  gem "tzinfo-data"
end

gem "wdm", "~> 0.1", platforms: %i[mingw x64_mingw mswin]
gem "http_parser.rb", "~> 0.6.0", platforms: %i[jruby]
