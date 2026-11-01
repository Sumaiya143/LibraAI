
/* Optional images can be added under /assets without changing the layout. */
(function(){
const hero=document.querySelector('.hero');
if(hero && window.LIBRA_HERO_IMAGE){hero.classList.add('has-image');hero.style.setProperty('--hero-image',`url("${window.LIBRA_HERO_IMAGE}")`)}
// Keep image slots as placeholders until the site owner supplies licensed images.
})();
