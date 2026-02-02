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
const isAuthenticated = document.body.dataset.authenticated === "true";

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
  if (
    socket &&
    (socket.readyState === WebSocket.OPEN ||
      socket.readyState === WebSocket.CONNECTING)
  ) {
    socket.close();
  }

  const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
  socket = new WebSocket(
    `${protocol}//${window.location.host}/ws/socket-server/`
  );

  socket.onmessage = (event) => {
    const { post_id, like_count } = JSON.parse(event.data);

    // Only update if this post is on the current page and element exists
    const countEl = document
      .getElementById(String(post_id))
      ?.querySelector(".count");
    if (countEl) {
      countEl.textContent = String(like_count);
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
  const heartEl = element.querySelector(".heart");
  const countEl = element.querySelector(".count");

  const isLiked = element.classList.contains("is-liked");

  // Store original state for potential rollback
  const originalHeart = heartEl.textContent;
  const originalCount = countEl.textContent;

  // Optimistic update: toggle heart and adjust count immediately
  heartEl.textContent = isLiked ? "♡" : "♥";
  countEl.textContent = isLiked
    ? Number(originalCount) - 1
    : Number(originalCount) + 1;
  element.classList.toggle("is-liked", !isLiked);

  try {
    const response = await fetch(element.href, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-CSRFToken": csrfToken,
      },
      body: JSON.stringify({ post: element.id }),
    });

    // Rollback if server rejected the request
    if (!response.ok) {
      console.warn("Like request failed with status:", response.status);
      heartEl.textContent = originalHeart;
      countEl.textContent = originalCount;
      element.classList.toggle("is-liked", isLiked);
    }
  } catch (error) {
    // Network error - rollback
    console.warn("Like request failed:", error);
    heartEl.textContent = originalHeart;
    countEl.textContent = originalCount;
    element.classList.toggle("is-liked", isLiked);
  }
}

/**
 * Fetch fresh like counts from server for all posts on page
 * Uses batch endpoint to get all counts in a single request
 * Used after back/forward navigation to prevent stale data
 */
async function refreshLikeCounts() {
  if (!postIds.length) return;

  try {
    const response = await fetch(
      `/api/v1/likes/batch/?ids=${postIds.join(",")}`,
      { cache: "no-store" }
    );
    if (!response.ok) {
      console.warn("Failed to refresh likes:", response.status);
      return;
    }

    const data = await response.json();

    for (const [postId, info] of Object.entries(data)) {
      const element = document.getElementById(postId);
      if (!element) continue;

      const heartEl = element.querySelector(".heart");
      const countEl = element.querySelector(".count");

      if (heartEl) {
        heartEl.textContent = info.liked ? "♥" : "♡";
      }
      element.classList.toggle("is-liked", info.liked);
      if (countEl) {
        countEl.textContent = info.count;
      }
    }
  } catch (error) {
    console.warn("Failed to refresh likes:", error);
  }
}

// =============================================================================
// PAGE LIFECYCLE - Handle navigation and visibility changes
// =============================================================================

// Initial WebSocket connection
connectWebSocket();

// Reconnect and refresh when returning to page via back/forward navigation
window.addEventListener("pageshow", (event) => {
  const navEntry = performance.getEntriesByType("navigation")[0];
  const isBackForward = navEntry?.type === "back_forward";

  // Refresh if:
  // - bfcache restoration (persisted=true), OR
  // - back/forward navigation (browser may serve cached HTML)
  if (event.persisted || isBackForward) {
    connectWebSocket(true);
    refreshLikeCounts();
  }
});

// Reconnect and refresh when tab becomes visible again (after being hidden)
document.addEventListener("visibilitychange", () => {
  if (document.visibilityState === "visible") {
    if (!socket || socket.readyState !== WebSocket.OPEN) {
      connectWebSocket();
      refreshLikeCounts();
    }
  }
});
