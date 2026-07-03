// YouTube embed behavior — the enhancement layer over two server-rendered
// patterns:
//
// 1. [data-facade] buttons (signature moments): thumbnail + play button in
//    the page; clicking swaps the button for an autoplay iframe in place.
// 2. [data-video-id] race-card buttons: open the shared <dialog> lightbox
//    and inject the iframe there; closing removes it (stops playback).
//
// In both cases the iframe uses youtube-nocookie.com and exists only after
// an explicit user click. Both triggers are server-rendered as plain <a>
// links to youtube.com, so with JS disabled they still work — this script
// intercepts the click and upgrades the experience to an inline embed.

function iframeFor(videoId: string, title: string): HTMLIFrameElement {
  const frame = document.createElement('iframe');
  frame.src = `https://www.youtube-nocookie.com/embed/${videoId}?autoplay=1&rel=0`;
  frame.title = title;
  frame.allow = 'accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture';
  frame.allowFullscreen = true;
  frame.style.cssText = 'width:100%;aspect-ratio:16/9;border:0;display:block;';
  return frame;
}

/* In-place facades (signature moments) */
document.addEventListener('click', (event) => {
  const facade = (event.target as HTMLElement).closest<HTMLElement>('[data-facade]');
  if (!facade) return;
  event.preventDefault();
  const { videoId, videoTitle } = facade.dataset;
  if (!videoId) return;
  const frame = iframeFor(videoId, videoTitle ?? 'YouTube video');
  facade.replaceWith(frame);
  frame.focus();
});

/* Dialog lightbox (race cards) */
const dialog = document.getElementById('video-dialog') as HTMLDialogElement | null;

if (dialog) {
  const slot = dialog.querySelector<HTMLElement>('.dialog-video')!;
  const heading = dialog.querySelector<HTMLElement>('.dialog-title')!;

  document.addEventListener('click', (event) => {
    const button = (event.target as HTMLElement).closest<HTMLElement>('[data-dialog-video]');
    if (!button) return;
    event.preventDefault();
    const { dialogVideo, dialogTitle } = button.dataset;
    if (!dialogVideo) return;
    heading.textContent = dialogTitle ?? '';
    slot.replaceChildren(iframeFor(dialogVideo, dialogTitle ?? 'Race highlights'));
    dialog.showModal();
  });

  // Closing by any route (Esc, ✕, backdrop click) must remove the iframe,
  // otherwise audio keeps playing into the void.
  dialog.addEventListener('close', () => slot.replaceChildren());
  dialog.addEventListener('click', (event) => {
    if (event.target === dialog) dialog.close(); // backdrop
  });
}
