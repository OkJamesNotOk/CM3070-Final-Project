<template>
	<main>
		<h1>NextTrack</h1>

		<div class="app-layout">

			<section class="search-panel">
				<input v-model="artist" placeholder="Enter artist name" />

				<div class="similar-artist-group">
					<label class="similar-artist-option">
						<input
							type="checkbox"
							v-model="includeSimilarArtists"
							:disabled="!artist.trim()"
						/>
						<span>Include similar artists</span>
					</label>
					<p class="similar-artist-help">
						Include tracks from artists related to the entered artist
					</p>
				</div>

				<input v-model="language" placeholder="Enter language e.g. English" />

				<input v-model="tags" class="tags-input" 
					placeholder="Enter genre/tags e.g. indie, chill"
				/>

				<input v-model="titleKeywords" placeholder="Enter title keywords" />

				<div class="button-container">
					<button @click="searchSong">Search</button>
					<button @click="clearSearch">Clear</button>
				</div>
			</section>

			<section class="results-panel">
				<div v-if="loading" class="loading-box">
					<div class="spinner"></div>
					<p>Loading recommendations... {{ formatElapsedTime(elapsedSeconds) }}</p>
				</div>

				<p v-else-if="loadTime !== null && !error" class="load-time">
					Recommendations loaded in {{ formatElapsedTime(loadTime) }}
				</p>

				<div v-if="error" class="error-box">
					<strong>Unable to load recommendations</strong>
					<p>{{ error }}</p>
				</div>

				<h2 v-if="songs.length">Recommended Songs</h2>
				<p v-if="songs.length" class="recommendation-count">
					Showing {{ visibleSongs.length }} of {{ songs.length }} recommendations
				</p>
				<section class="recommendation-grid">
					<div
						v-for="(song, index) in visibleSongs"
						:key="song.mbid"
						:class="['song-card', index % 2 == 0 ? 'card-blue' : 'card-purple']"
					>
						<div class="card-header">
							<div class="card-title-area">
								<span class="rank-badge">#{{ index + 1 }}</span>
								<div>
									<h3>{{ song.title }}</h3>
									<p class="artist-name">{{ song.artist }}</p>
									<span v-if="song.is_related_artist" class="related-artist-badge">
										Related Artist
									</span>
								</div>
							</div>
							<span class="score-badge">{{ formatScore(song.final_score) }}</span>
						</div>

						<div v-if="song.length || (song.tags && song.tags.length)" class="quick-info">
							<span v-if="song.length" class="quick-length">{{ song.length }}</span>
							<div v-if="song.tags && song.tags.length" class="quick-tags">
								<span class="quick-label">Tags</span>
								<span v-for="tag in song.tags.slice(0, 2)" :key="tag" class="quick-tag">{{ tag }}</span>
							</div>
						</div>

						<button class="toggle-all-details" @click="toggleAllDetails($event)">
							Toggle all details
						</button>

						<!-- Expandable area -->
						<details class="expandable-details">
							<summary>Track details</summary>

							<div
								v-if="getYouTubeEmbedUrl(song)"
								class="youtube-preview"
							>
								<iframe
									:src="getYouTubeEmbedUrl(song)"
									title="YouTube music preview"
									loading="lazy"
									allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
									allowfullscreen
								></iframe>
							</div>

							<!--  metadata stuffs -->
							<div class="metadata-grid">
								<div v-if="song.language">
									<span class="metadata-label">Language</span>
									<span>{{ song.language }}</span>
								</div>

								<div v-if="song.length">
									<span class="metadata-label">Length</span>
									<span>{{ song.length }}</span>
								</div>

								<div v-if="song.release">
									<span class="metadata-label">Release</span>
									<span>{{ song.release }}</span>
								</div>
							</div>

							<!-- Popularity -->
							<div
								v-if="song.listeners || song.playcount"
								class="stats-row"
							>
								<div v-if="song.listeners" class="stat-box">
									<strong>{{ formatNumber(song.listeners) }}</strong>
									<span>Listeners</span>
								</div>

								<div v-if="song.playcount" class="stat-box">
									<strong>{{ formatNumber(song.playcount) }}</strong>
									<span>Plays</span>
								</div>
							</div>

							<div v-if="Array.isArray(song.tags) && song.tags.length" class="tag-section">
								<p class="section-label">Tags</p>

								<div class="tag-list">
									<span
										v-for="tag in song.tags"
										:key="tag"
										class="tag-chip"
									>
										{{ tag }}
									</span>
								</div>
							</div>

							<!-- non youtube links -->
							<div
								v-if="getOtherLinks(song).length"
								class="external-links"
							>
								<p class="section-label">Other links</p>

								<div class="link-list">
									<a
										v-for="link in getOtherLinks(song)"
										:key="link.url"
										:href="link.url"
										target="_blank"
										rel="noopener noreferrer"
										class="external-link"
									>
										{{ formatLinkType(link.type) }}
									</a>
								</div>
							</div>

							<p>
								<strong>MusicBrainz ID:</strong>
								{{ song.mbid || 'N/A' }}
							</p>
						</details>

						<details v-if="song.score_breakdown" class="expandable-details">
							<summary>Why Recommended?</summary>
							<p><strong>Genre/Tag:</strong> {{ formatScore(song.score_breakdown.tag_score) }}</p>
							<p><strong>Artist:</strong> {{ formatScore(song.score_breakdown.artist_score) }}</p>
							<p><strong>Language:</strong> {{ formatScore(song.score_breakdown.language_score) }}</p>
							<p><strong>Keyword:</strong> {{ formatScore(song.score_breakdown.keyword_score) }}</p>
							<p><strong>Popularity:</strong> {{ formatScore(song.popularity_score) }}</p>
							<p><strong>Final score:</strong> {{ formatScore(song.final_score) }}</p>
						</details>
					</div>
				</section>

				<div v-if="hasMoreSongs" class="load-more-container">
					<button class="load-more-button" @click="loadMoreSongs">Load 5 More</button>
				</div>
			</section>			

		</div>
	</main>
</template>

<script src="../scripts/nexttrack.js"></script>

<style src="../assets/css/nexttrack.css" scoped></style>