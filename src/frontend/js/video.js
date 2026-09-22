/* YouTube playback, lead-in timing and embed error handling. */

var player;
var youtubePlayerReady = false;
var pendingVideoStart = null;
var currentYouTubeVideoId = null;
var currentVideoLeadSeconds = 5;
var youtubePlayerErrorCode = null;

function ensureYouTubePlayerHost() {
    const videoContainer = document.getElementById('videoContainer');
    if (!videoContainer || document.getElementById('player')) return;
    const playerHost = document.createElement('div');
    playerHost.id = 'player';
    videoContainer.prepend(playerHost);
}

function destroyYouTubePlayer() {
    pendingVideoStart = null;
    youtubePlayerReady = false;
    if (player) {
        try {
            if (typeof player.stopVideo === 'function') player.stopVideo();
            if (typeof player.destroy === 'function') player.destroy();
        } catch (error) {
            console.warn('Could not fully reset the YouTube player.', error);
        }
    }
    player = null;
    ensureYouTubePlayerHost();
}

function createYouTubePlayer() {
    if (player || !currentYouTubeVideoId || !window.YT || typeof YT.Player !== 'function') return;
    ensureYouTubePlayerHost();
    youtubePlayerReady = false;
    player = new YT.Player('player', {
        height: '100%',
        width: '100%',
        playerVars: {
            'playsinline': 1,
            'controls': 1,
            'hl': 'en',
            'rel': 0,
            'origin': window.location.origin
        },
        events: {
            'onReady': onYouTubePlayerReady,
            'onError': onYouTubePlayerError
        }
    });
}

function setYouTubeVideo(videoId, leadSeconds = 5) {
    const nextVideoId = String(videoId || '').trim() || null;
    const numericLead = Number(leadSeconds);
    const nextLeadSeconds = Number.isFinite(numericLead)
        ? Math.max(0, Math.min(15, numericLead))
        : 5;
    const videoChanged = nextVideoId !== currentYouTubeVideoId;

    currentYouTubeVideoId = nextVideoId;
    currentVideoLeadSeconds = nextLeadSeconds;
    youtubePlayerErrorCode = null;
    updateYouTubePlayerNotice();
    pendingVideoStart = null;

    if (!currentYouTubeVideoId) {
        destroyYouTubePlayer();
        return;
    }

    if (!player) createYouTubePlayer();
    if (!videoChanged || !youtubePlayerReady || !player) return;
    if (typeof player.cueVideoById === 'function') {
        player.cueVideoById({ videoId: currentYouTubeVideoId, startSeconds: 0 });
    }
}

window.setYouTubeVideo = setYouTubeVideo;

function startYouTubeAt(seconds, leadSeconds = currentVideoLeadSeconds) {
    const requestedLead = Number(leadSeconds);
    const safeLeadSeconds = Number.isFinite(requestedLead)
        ? Math.max(0, Math.min(15, requestedLead))
        : currentVideoLeadSeconds;
    const startSeconds = Math.max(0, Number(seconds) - safeLeadSeconds);
    if (!currentYouTubeVideoId || !Number.isFinite(startSeconds)) return;
    pendingVideoStart = startSeconds;

    if (!youtubePlayerReady || !player || typeof player.getPlayerState !== 'function') return;

    const state = player.getPlayerState();
    if (state === YT.PlayerState.UNSTARTED || state === YT.PlayerState.CUED) {
        // loadVideoById is reliable before the first playback; seekTo alone is often ignored here.
        player.loadVideoById({ videoId: currentYouTubeVideoId, startSeconds });
    } else {
        player.seekTo(startSeconds, true);
        player.playVideo();
    }
    pendingVideoStart = null;
}

window.playVideoAt = startYouTubeAt;

function updateYouTubePlayerNotice(message = '') {
    const notice = document.getElementById('youtubePlayerNotice');
    const noticeText = document.getElementById('youtubePlayerNoticeText');
    const noticeLink = document.getElementById('youtubePlayerNoticeLink');
    if (!notice || !noticeText || !noticeLink) return;

    notice.style.display = message ? 'block' : 'none';
    noticeText.textContent = message ? `${message} ` : '';
    noticeLink.href = currentYouTubeVideoId
        ? `https://www.youtube.com/watch?v=${encodeURIComponent(currentYouTubeVideoId)}`
        : '#';
}

function onYouTubePlayerReady(event) {
    if (event?.target && event.target !== player) return;
    if (!currentYouTubeVideoId) {
        destroyYouTubePlayer();
        return;
    }
    youtubePlayerReady = true;
    if (pendingVideoStart !== null) {
        startYouTubeAt(pendingVideoStart + currentVideoLeadSeconds);
    } else if (currentYouTubeVideoId) {
        player.cueVideoById({ videoId: currentYouTubeVideoId, startSeconds: 0 });
    }
}

function onYouTubePlayerError(event) {
    if (event?.target && event.target !== player) return;
    youtubePlayerErrorCode = Number(event?.data);
    const messages = {
        100: 'This video was removed or is private.',
        101: 'The video owner does not allow playback inside other websites.',
        150: 'The video owner does not allow playback inside other websites.',
        153: 'YouTube could not identify the website that embedded this player.'
    };
    updateYouTubePlayerNotice(messages[youtubePlayerErrorCode] || 'YouTube could not play this video here.');
    console.warn(`YouTube player error ${youtubePlayerErrorCode} for video ${currentYouTubeVideoId || "unknown"}.`);
}

function onYouTubeIframeAPIReady() {
    createYouTubePlayer();
}
