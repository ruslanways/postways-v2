/*
using Fetch-api to like posts
by making POST-requests to Django LikeCreateDestroyAPIView
*/
// get csrftoken for POST-request with Fetch
const csrftoken = getCookie("csrftoken");
// Get all "like" <div>'s elements to operate with
const likes = document.querySelectorAll(".like");
// Add addEventListener to all .like element only if the user is authenticated
if (document.getElementById("user") && likes.length) {
  likes.forEach((like) => like.addEventListener("click", makeLike));
}

// Create a WebSocket for live update likes
const likeSocket = new WebSocket(
  `wss://${window.location.host}/ws/socket-server/`
);
// Get post.id exists on a current page
const posts_on_page = [];
likes.forEach((like) => posts_on_page.push(like.id));
// Console log of closed unexpectedly
likeSocket.onclose = function (e) {
  console.warn("WebSocket have closed unexpectedly");
};

likeSocket.onmessage = function (e) {
  let data = JSON.parse(e.data);
  if (posts_on_page.includes(data.post_id)) {
    let like = document.getElementById(data.post_id);
    const old_heart = like.innerHTML.trim().split(" ")[0];
    like.innerHTML = old_heart + " " + data.like_count;
  }
};
// Send a POST request to add or delete like
// Update a color and number of heart
async function makeLike(evt) {
  // Prevent default browser following link behaviour
  // We could use not <a>, but then it would not be in the form of link-hand
  evt.preventDefault();
  // Get current heart+number
  let content = this.innerHTML.trim().split(" ");
  // Change hear to opposite color and increment or decrement number
  if (content[0].charCodeAt(0) === 10084) {
    content[0] = "&#9825;";
    --content[1];
  } else {
    content[0] = "&#10084;";
    ++content[1];
  }
  this.innerHTML = `${content[0]} ${content[1]}`;
  try {
    // 'this' reffers to as addEventListener object abs url
    await fetch(this.href, {
      method: "POST",
      headers: {
        "Content-Type": "application/json;charset=utf-8",
        "X-CSRFToken": csrftoken,
      },
      body: JSON.stringify({ post: this.id }),
    });
  } catch (err) {
    // If error happend while fetching - the error will show in console,
    // but no like correction happend, because it automatically checks
    // in WebSocket below
    console.warn(err);
  }
}
// Get cookie for any needs (e.g. csrftoken)
function getCookie(name) {
  let cookieValue = null;
  if (document.cookie && document.cookie !== "") {
    const cookies = document.cookie.split(";");
    for (let i = 0; i < cookies.length; i++) {
      const cookie = cookies[i].trim();
      // Does this cookie string begin with the name we want?
      if (cookie.substring(0, name.length + 1) === name + "=") {
        cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
        break;
      }
    }
  }
  return cookieValue;
}
