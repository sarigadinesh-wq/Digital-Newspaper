// Client-side interactions for The Daily Gazette

document.addEventListener("DOMContentLoaded", () => {
    // Application State
    let state = {
        currentCategory: "general",
        currentCountry: "us",
        currentView: "headlines", // "headlines" or "sources"
        activeSource: null,
        articlesInMemory: [],
        sourcesInMemory: []
    };

    // DOM Elements
    const dateDisplay = document.getElementById("current-date-display");
    const categoryLinks = document.querySelectorAll(".nav-item");
    const countrySelect = document.getElementById("country-select");
    const searchInput = document.getElementById("search-input");
    const searchBtn = document.getElementById("search-btn");
    const toggleSourcesBtn = document.getElementById("toggle-sources-btn");
    const backToHeadlinesBtn = document.getElementById("back-to-headlines-btn");
    const fallbackAlert = document.getElementById("fallback-alert");
    
    // Layout Containers
    const newsLayout = document.getElementById("news-layout");
    const sidebarContainer = document.getElementById("sidebar-container");
    const articlesContainer = document.getElementById("articles-container");
    const sourcesBrowserContainer = document.getElementById("sources-browser-container");
    
    // Insertion Slots
    const leadArticleSlot = document.getElementById("lead-article-slot");
    const subHeadlinesGrid = document.getElementById("sub-headlines-grid");
    const sourcesSidebarList = document.getElementById("sources-sidebar-list");
    const sourcesGrid = document.getElementById("sources-grid");

    // Unsplash Category Fallbacks for missing article images (satisfying color-pop requirement)
    const categoryImages = {
        general: "https://images.unsplash.com/photo-1504711434969-e33886168f5c?auto=format&fit=crop&w=800&q=80",
        business: "https://images.unsplash.com/photo-1507679799987-c73779587ccf?auto=format&fit=crop&w=800&q=80",
        technology: "https://images.unsplash.com/photo-1518770660439-4636190af475?auto=format&fit=crop&w=800&q=80",
        science: "https://images.unsplash.com/photo-1507413245164-6160d8298b31?auto=format&fit=crop&w=800&q=80",
        health: "https://images.unsplash.com/photo-1506126613408-eca07ce68773?auto=format&fit=crop&w=800&q=80",
        sports: "https://images.unsplash.com/photo-1461896836934-ffe607ba8211?auto=format&fit=crop&w=800&q=80",
        entertainment: "https://images.unsplash.com/photo-1514525253161-7a46d19cd819?auto=format&fit=crop&w=800&q=80"
    };

    // Set Date Banner
    const initDateBanner = () => {
        const options = { weekday: 'long', year: 'numeric', month: 'long', day: 'numeric' };
        const today = new Date();
        dateDisplay.textContent = today.toLocaleDateString('en-US', options);
    };

    // Helper: Formats Date Strings to classic newspaper print style
    const formatArticleDate = (isoString) => {
        if (!isoString) return "";
        try {
            const date = new Date(isoString);
            return date.toLocaleDateString("en-US", {
                month: "short",
                day: "numeric",
                year: "numeric"
            }) + " at " + date.toLocaleTimeString("en-US", {
                hour: "2-digit",
                minute: "2-digit"
            });
        } catch {
            return isoString;
        }
    };

    // Helper: Get fallback image for specific category
    const getFallbackImage = (categoryName) => {
        const key = (categoryName || "general").toLowerCase();
        return categoryImages[key] || categoryImages.general;
    };

    // Fetch Headlines
    const fetchHeadlines = async () => {
        showLoadingState();
        try {
            const res = await fetch(`/api/top-headlines?category=${state.currentCategory}&country=${state.currentCountry}`);
            const data = await res.json();
            
            // Toggle fallback notification
            if (data.is_fallback) {
                fallbackAlert.classList.remove("d-none");
            } else {
                fallbackAlert.classList.add("d-none");
            }

            state.articlesInMemory = data.articles || [];
            renderArticles(state.articlesInMemory);
        } catch (err) {
            console.error("Headlines fetch error:", err);
            renderError("Failed to communicate with news backend server.");
        }
    };

    // Fetch Sources
    const fetchSources = async () => {
        try {
            const res = await fetch(`/api/sources`);
            const data = await res.json();
            state.sourcesInMemory = data.sources || [];
            renderSidebarSources(state.sourcesInMemory);
            renderSourcesBrowser(state.sourcesInMemory);
        } catch (err) {
            console.error("Sources fetch error:", err);
        }
    };

    // Fetch Everything from Source
    const fetchSourceFeed = async (sourceId, sourceName) => {
        showLoadingState();
        try {
            const res = await fetch(`/api/everything/${sourceId}`);
            const data = await res.json();
            
            if (data.is_fallback) {
                fallbackAlert.classList.remove("d-none");
            } else {
                fallbackAlert.classList.add("d-none");
            }

            // Update title to specify source name
            document.getElementById("masthead-main-title").textContent = (sourceName || 'News Wire').toUpperCase();
            
            state.articlesInMemory = data.articles || [];
            renderArticles(state.articlesInMemory);
            
            // Revert back to news mode if we were in sources grid
            switchToHeadlinesView();
        } catch (err) {
            console.error("Source feed fetch error:", err);
            renderError(`Could not fetch news articles from ${sourceName}.`);
        }
    };

    // Render Articles Feed
    const renderArticles = (articles) => {
        leadArticleSlot.innerHTML = "";
        subHeadlinesGrid.innerHTML = "";

        if (!articles || articles.length === 0) {
            subHeadlinesGrid.innerHTML = `
                <div class="col-12 text-center py-5">
                    <p class="italic text-muted">"No correspondence found on the chosen wire."</p>
                </div>
            `;
            return;
        }

        // Article 1: Lead Article Layout
        const lead = articles[0];
        const leadImg = lead.urlToImage || getFallbackImage(state.currentCategory);
        const leadSource = lead.source?.name || "Independent Wire";
        const leadAuthor = lead.author ? `By ${lead.author}` : "By Staff Correspondent";
        const leadDate = formatArticleDate(lead.publishedAt);

        leadArticleSlot.innerHTML = `
            <div class="lead-article p-4">
                <div class="row g-4 align-items-center">
                    <div class="col-lg-6">
                        <div class="lead-image-container">
                            <img src="${leadImg}" alt="Lead Article Image" class="lead-image" onerror="this.src='${getFallbackImage(state.currentCategory)}'">
                        </div>
                    </div>
                    <div class="col-lg-6">
                        <div class="meta-text mb-2">${leadSource} &bull; ${leadDate}</div>
                        <h2 class="lead-title"><a href="${lead.url}" target="_blank">${lead.title}</a></h2>
                        <div class="meta-text mb-3 italic fw-normal">${leadAuthor}</div>
                        <p class="lead-desc mb-3">${lead.description || "Refer to the wire link for the complete text details of this editorial."}</p>
                        <a href="${lead.url}" target="_blank" class="btn btn-sm btn-dark text-uppercase fw-bold">Read Full Dispatch</a>
                    </div>
                </div>
            </div>
        `;

        // Remaining Articles: Standard Cards in dynamic columns
        const subArticles = articles.slice(1, 10); // Display next 9 articles
        subArticles.forEach((art, index) => {
            const artImg = art.urlToImage || getFallbackImage(state.currentCategory);
            const artSource = art.source?.name || "Press Release";
            const artAuthor = art.author ? `By ${art.author}` : "Staff Writer";
            const artDate = formatArticleDate(art.publishedAt);
            
            const col = document.createElement("div");
            col.className = "col-md-6 col-lg-4 mb-4";
            col.innerHTML = `
                <div class="article-card d-flex flex-column h-100 p-3">
                    <div class="card-image-container mb-3">
                        <img src="${artImg}" alt="Article Image" class="card-image" onerror="this.src='${getFallbackImage(state.currentCategory)}'">
                    </div>
                    <div class="meta-text mb-1">${artSource}</div>
                    <h4 class="article-title"><a href="${art.url}" target="_blank">${art.title}</a></h4>
                    <div class="meta-text mb-2 italic small fw-normal">${artAuthor} &bull; ${artDate}</div>
                    <p class="article-desc flex-grow-1">${art.description || "The chronicle dispatch continues online. Select link for details."}</p>
                    <hr class="my-2">
                    <div class="text-end">
                        <a href="${art.url}" target="_blank" class="small text-dark fw-bold text-decoration-none text-uppercase">Full Text &rarr;</a>
                    </div>
                </div>
            `;
            subHeadlinesGrid.appendChild(col);
        });
    };

    // Render Sidebar News Agencies List
    const renderSidebarSources = (sources) => {
        sourcesSidebarList.innerHTML = "";
        
        // Show up to 10 key sources on sidebar
        const subset = sources.slice(0, 10);
        subset.forEach(src => {
            const item = document.createElement("a");
            item.className = "list-group-item list-group-item-action border-0 py-2 small-meta text-uppercase";
            item.textContent = src.name;
            item.setAttribute("data-id", src.id);
            item.addEventListener("click", () => {
                state.activeSource = src.id;
                fetchSourceFeed(src.id, src.name);
            });
            sourcesSidebarList.appendChild(item);
        });
    };

    // Render Full Sources Browser
    const renderSourcesBrowser = (sources) => {
        sourcesGrid.innerHTML = "";
        if (!sources || sources.length === 0) {
            sourcesGrid.innerHTML = `<div class="col-12 text-center text-muted italic">"No agencies listed."</div>`;
            return;
        }

        sources.forEach(src => {
            const col = document.createElement("div");
            col.className = "col-md-6 col-lg-4 mb-4";
            col.innerHTML = `
                <div class="source-card p-4 h-100 d-flex flex-column justify-content-between" data-id="${src.id}">
                    <div>
                        <span class="meta-text">${src.category || 'general'} &bull; ${(src.country || '').toUpperCase()}</span>
                        <h4 class="mt-2 mb-3">${src.name}</h4>
                        <p class="small text-muted italic">${src.description || "No official directory brief available."}</p>
                    </div>
                    <div class="mt-3 text-end">
                        <span class="btn btn-sm btn-outline-dark text-uppercase fw-bold">Load Dispatch Wire</span>
                    </div>
                </div>
            `;

            col.querySelector(".source-card").addEventListener("click", () => {
                state.activeSource = src.id;
                fetchSourceFeed(src.id, src.name);
            });

            sourcesGrid.appendChild(col);
        });
    };

    // Loading State DOM indicators
    const showLoadingState = () => {
        leadArticleSlot.innerHTML = `
            <div class="text-center py-5">
                <div class="spinner-border text-dark" role="status">
                    <span class="visually-hidden">Loading...</span>
                </div>
                <p class="italic text-muted mt-3">Teletype wire incoming. Please stand by...</p>
            </div>
        `;
        subHeadlinesGrid.innerHTML = "";
    };

    // Error rendering
    const renderError = (message) => {
        leadArticleSlot.innerHTML = `
            <div class="alert alert-custom p-4 text-center">
                <h4 class="serif-font text-white mb-2">Teletype Failure</h4>
                <p class="mb-0 text-muted small">${message}</p>
            </div>
        `;
        subHeadlinesGrid.innerHTML = "";
    };

    // View Switching Controllers
    const switchToHeadlinesView = () => {
        state.currentView = "headlines";
        
        sidebarContainer.classList.remove("d-none");
        articlesContainer.classList.remove("d-none");
        sourcesBrowserContainer.classList.add("d-none");
        
        toggleSourcesBtn.classList.remove("d-none");
        backToHeadlinesBtn.classList.add("d-none");
    };

    const switchToSourcesView = () => {
        state.currentView = "sources";
        
        sidebarContainer.classList.add("d-none");
        articlesContainer.classList.add("d-none");
        sourcesBrowserContainer.classList.remove("d-none");
        
        toggleSourcesBtn.classList.add("d-none");
        backToHeadlinesBtn.classList.remove("d-none");
    };

    // Category click handler
    categoryLinks.forEach(link => {
        link.addEventListener("click", (e) => {
            e.preventDefault();
            
            // Revert masthead title if it was custom source
            document.getElementById("masthead-main-title").textContent = "THE DAILY GAZETTE";
            
            categoryLinks.forEach(l => l.classList.remove("active"));
            link.classList.add("active");
            
            state.currentCategory = link.getAttribute("data-category");
            state.activeSource = null;
            
            switchToHeadlinesView();
            fetchHeadlines();
        });
    });

    // Country Select Handler
    countrySelect.addEventListener("change", (e) => {
        state.currentCountry = e.target.value;
        fetchHeadlines();
    });

    // Toggle Sources
    toggleSourcesBtn.addEventListener("click", () => {
        switchToSourcesView();
    });

    // Back to headlines
    backToHeadlinesBtn.addEventListener("click", () => {
        // Reset title
        document.getElementById("masthead-main-title").textContent = "THE DAILY GAZETTE";
        switchToHeadlinesView();
        fetchHeadlines();
    });

    // Search Trigger (Local filtering based on current loaded headlines)
    const performSearch = () => {
        const query = searchInput.value.toLowerCase().trim();
        if (query === "") {
            renderArticles(state.articlesInMemory);
            return;
        }

        const filtered = state.articlesInMemory.filter(art => {
            return (art.title && art.title.toLowerCase().includes(query)) || 
                   (art.description && art.description.toLowerCase().includes(query)) ||
                   (art.content && art.content.toLowerCase().includes(query));
        });

        renderArticles(filtered);
    };

    searchBtn.addEventListener("click", performSearch);
    searchInput.addEventListener("keyup", (e) => {
        if (e.key === "Enter") {
            performSearch();
        }
    });

    // Initial load
    initDateBanner();
    fetchHeadlines();
    fetchSources();
});
