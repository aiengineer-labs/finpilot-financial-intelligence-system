export const THEME_STORAGE_KEY = "fp-theme";

/** Applied before first paint so a stored light/dark choice never flashes. */
export const themeBootScript = `try{var t=localStorage.getItem("${THEME_STORAGE_KEY}");if(t==="light"||t==="dark")document.documentElement.dataset.theme=t}catch(e){}`;
