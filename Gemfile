source "https://rubygems.org"

# GitHub Pages gem — garante compatibilidade com o ambiente do GitHub Pages
gem "github-pages", group: :jekyll_plugins

# Plugins adicionais
group :jekyll_plugins do
  gem "jekyll-seo-tag"
  gem "jekyll-sitemap"
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
