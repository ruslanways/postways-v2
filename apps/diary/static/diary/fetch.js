/**
 * Real-time likes system using Fetch API and WebSocket
 *
 * Features:
 * - Optimistic UI updates when liking/unliking posts
 * - Real-time like count sync via WebSocket for all users
 * - Automatic reconnection on back/forward navigation (bfcache)
 * - Fresh data fetch after navigation to prevent stale state
 */

// =============================================================================
// UTILITIES
// =============================================================================

/**
 * Extract a cookie value by name
 */
function getCookie(name) {
  if (!document.cookie) return null;

  const cookie = document.cookie
    .split(";")
    .map((c) => c.trim())
    .find((c) => c.startsWith(name + "="));

  return cookie ? decodeURIComponent(cookie.split("=")[1]) : null;
}

// =============================================================================
// INITIALIZATION
// =============================================================================

const csrfToken = getCookie("csrftoken");
const likeElements = document.querySelectorAll(".like");
const postIds = Array.from(likeElements).map((el) => el.id);
const isAuthenticated = Boolean(document.getElementById("user"));

// Only attach click handlers for authenticated users
if (isAuthenticated && likeElements.length) {
  likeElements.forEach((el) => el.addEventListener("click", handleLikeClick));
}

// =============================================================================
// WEBSOCKET - Real-time like updates
// =============================================================================

let socket = null;

/**
 * Create WebSocket connection for real-time like updates
 * All users (authenticated and anonymous) receive live updates
 */
function connectWebSocket(forceReconnect = false) {
  if (!postIds.length) return;

  // Skip if already connected (unless forcing reconnect)
  if (socket && socket.readyState === WebSocket.OPEN && !forceReconnect) return;

  // Close existing connection before creating new one
  if (socket && (socket.readyState === WebSocket.OPEN || socket.readyState === WebSocket.CONNECTING)) {
    socket.close();
  }

  const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
  socket = new WebSocket(`${protocol}//${window.location.host}/ws/socket-server/`);

  socket.onmessage = (event) => {
    const { post_id, like_count } = JSON.parse(event.data);

    // Only update if this post is on the current page
    if (postIds.includes(post_id)) {
      const element = document.getElementById(post_id);
      const currentHeart = element.innerHTML.trim().split(" ")[0];
      element.innerHTML = `${currentHeart} ${like_count}`;
    }
  };

  socket.onclose = () => console.warn("WebSocket closed");
}

// =============================================================================
// LIKE FUNCTIONALITY
// =============================================================================

/**
 * Handle like/unlike click with optimistic UI update
 * Updates UI immediately, then sends request to server
 */
async function handleLikeClick(event) {
  event.preventDefault();

  const element = this;
  const [heart, count] = element.innerHTML.trim().split(" ");
  const isLiked = heart.charCodeAt(0) === 10084; // ❤ (filled heart)

  // Optimistic update: toggle heart and adjust count immediately
  const newHeart = isLiked ? "&#9825;" : "&#10084;"; // ♡ or ❤
  const newCount = isLiked ? Number(count) - 1 : Number(count) + 1;
  element.innerHTML = `${newHeart} ${newCount}`;

  try {
    await fetch(element.href, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-CSRFToken": csrfToken,
      },
      body: JSON.stringify({ post: element.id }),
    });
    // Server broadcasts update via WebSocket, which syncs all clients
  } catch (error) {
    // On error, WebSocket will eventually sync the correct state
    console.warn("Like request failed:", error);
  }
}

/**
 * Fetch fresh like counts from server for all posts on page
 * Used after back/forward navigation to prevent stale data
 */
async function refreshLikeCounts() {
  const requests = postIds.map(async (postId) => {
    try {
      const response = await fetch(`/likes_count_on_post/${postId}/`);
      if (response.ok) {
        document.getElementById(postId).innerHTML = await response.text();
      }
    } catch (error) {
      console.warn(`Failed to refresh likes for post ${postId}:`, error);
    }
  });

  await Promise.all(requests);
}

// =============================================================================
// PAGE LIFECYCLE - Handle navigation and visibility changes
// =============================================================================

// Initial WebSocket connection
connectWebSocket();

// Reconnect and refresh when page is restored from bfcache (back/forward navigation)
window.addEventListener("pageshow", (event) => {
  if (event.persisted) {
    connectWebSocket(true);
    refreshLikeCounts();
  }
});

// Reconnect when tab becomes visible again (after being hidden)
document.addEventListener("visibilitychange", () => {
  if (document.visibilityState === "visible") {
    if (!socket || socket.readyState !== WebSocket.OPEN) {
      connectWebSocket();
    }
  }
});
