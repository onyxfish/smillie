BUCKET    ?= smilliediaries.com
CF_DIST   ?= REPLACE_WITH_DIST_ID

.PHONY: dev build deploy upload-images clean install

# Install npm dependencies
install:
	npm install

# Clean build artifacts
clean:
	rm -rf dist pagefind-source site/public/data

# Development: build data + pagefind index for one year, then start dev server
# Run `make dev` then open http://localhost:5173
# Search is served from dist/pagefind/ via a dev-server middleware in vite.config.js
dev: install
	python3 build_site.py
	npx pagefind --site pagefind-source --output-path dist/pagefind
	@echo "Starting image server on port 8001 (background)..."
	@python3 -m http.server 8001 --directory data > /dev/null 2>&1 &
	npm run dev

# Full production build
build: install
	python3 build_site.py
	npm run build
	npx pagefind --site pagefind-source --output-path dist/pagefind

# Deploy to S3 + CloudFront
deploy: build
	# HTML files: no-cache (always revalidate)
	aws s3 sync dist/ s3://$(BUCKET)/ \
	  --exclude "assets/*" --exclude "data/*" --exclude "pagefind/*" \
	  --cache-control "no-cache"
	# Hashed assets: immutable (1 year cache)
	aws s3 sync dist/assets/ s3://$(BUCKET)/assets/ \
	  --cache-control "public,max-age=31536000,immutable"
	# Data files: 30-day cache
	aws s3 sync dist/data/ s3://$(BUCKET)/data/ \
	  --cache-control "public,max-age=2592000"
	# Search index: 30-day cache
	aws s3 sync dist/pagefind/ s3://$(BUCKET)/pagefind/ \
	  --cache-control "public,max-age=2592000"
# 	# Invalidate CloudFront cache
# 	aws cloudfront create-invalidation \
# 	  --distribution-id $(CF_DIST) --paths "/*"

# Upload diary images to S3 (one-time, ~6.8 GB)
upload-images:
	aws s3 sync data/ s3://$(BUCKET)/images/ \
	  --exclude "mets.json" \
	  --cache-control "public,max-age=31536000,immutable"

# Build data only (for development)
data:
	python3 build_site.py

# Build data for a single year
data-year:
	python3 build_site.py --year $(YEAR)
