export default {
    data() {
        return {
            artist: '',
            language: '',
            tags: '',
            titleKeywords: '',
            songs: [],
            displayedCount: 5,
            loading: false,
            elapsedSeconds: 0,
            loadTime: null,
            loadingTimer: null,
            error: '',
            includeSimilarArtists: false,
        }
    },

    computed: 
    {
        visibleSongs() {
            return this.songs.slice(0, this.displayedCount)
        },
        hasMoreSongs() {
            return this.displayedCount < this.songs.length
        }
    },

    methods:
    {        
        async searchSong() {
            this.loading = true
            this.error = ''
            this.songs = []
            this.elapsedSeconds = 0
            this.loadTime = null

            // make timer for how long request gonna take
            const startTime = Date.now()

            clearInterval(this.loadingTimer)
            this.loadingTimer = setInterval(() => {
                this.elapsedSeconds = Math.floor((Date.now() - startTime) / 1000)
            }, 1000)

            // build search query parameters with search fields
            const params = new URLSearchParams()

            if (this.artist) params.append('artist', this.artist)
            if (this.language) params.append('language', this.language)
            if (this.tags) params.append('tags', this.tags)
            if (this.titleKeywords) params.append('title_keywords', this.titleKeywords)
                
            params.append('include_similar_artists',this.includeSimilarArtists)

            try {
                const response = await fetch(
                    `/api/song/?${params.toString()}`
                )

                if (!response.ok) {
                    throw new Error('Search failed')
                }

                const data = await response.json()
                this.songs = data.recommendations || []
                this.displayedCount = 5
                
            } catch (error) {
                this.error = 'Could not load recommendations. Please try again.'
            } finally {
                this.loadTime = Math.floor((Date.now() - startTime) / 1000)
                this.elapsedSeconds = this.loadTime
                clearInterval(this.loadingTimer)
                this.loadingTimer = null
                this.loading = false
            }
        },

        getYouTubeEmbedUrl(song) {
            const links = song.links || []

            // find youtube link
            const link = links.find(link =>
                link.url &&
                (
                    link.url.includes('youtube.com/watch?v=') ||
                    link.url.includes('youtu.be/')
                )
            )

            if (!link) return ''

            if (link.url.includes('youtube.com/watch?v=')) {
                const videoId = link.url.split('v=')[1].split('&')[0]
                return `https://www.youtube.com/embed/${videoId}`
            }

            if (link.url.includes('youtu.be/')) {
                const videoId = link.url.split('youtu.be/')[1].split('?')[0]
                return `https://www.youtube.com/embed/${videoId}`
            }

            return ''
        },

        getOtherLinks(song) {
            const links = song.links || []

            // remove youtbe link in embedded player
            return links.filter(link => {
                if (!link.url) return false

                const url = link.url.toLowerCase()

                return !(
                    url.includes('youtube.com') ||
                    url.includes('youtu.be')
                )
            })
        },

        formatLinkType(type) {
            if (!type) return 'Open link'

            return type
                .replace(/-/g, ' ')
                .replace(/\b\w/g, char => char.toUpperCase())
        },

        formatNumber(value) {
            if (!value) return '0'

            return new Intl.NumberFormat('en', {
                notation: 'compact',
                maximumFractionDigits: 1
            }).format(value)
        },

        formatScore(value) {
            if (typeof value !== 'number') return 'Not used'
            return `${(value * 100).toFixed(1)}%`
        },

        loadMoreSongs() {
            this.displayedCount = Math.min(this.displayedCount + 5, this.songs.length)
        },

        clearSearch() {
            this.artist = ''
            this.language = ''
            this.tags = ''
            this.titleKeywords = ''
            this.songs = []
            this.includeSimilarArtists = false
            this.displayedCount = 5
            this.elapsedSeconds = 0
            this.loadTime = null
            clearInterval(this.loadingTimer)
            this.loadingTimer = null
            this.error = ''
        },

        formatElapsedTime(seconds) {
            const minutes = Math.floor(seconds / 60)
            const remainingSeconds = seconds % 60
            return `${minutes}:${remainingSeconds.toString().padStart(2, '0')}`
        },

        toggleAllDetails(event) {
            const card = event.currentTarget.closest('.song-card');
            const details = card.querySelectorAll('.expandable-details');
            const shouldOpen = [...details].some(detail => !detail.open);
            details.forEach(detail => detail.open = shouldOpen);
        },
    }
}