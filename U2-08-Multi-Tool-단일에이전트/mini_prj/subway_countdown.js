const activeTimers = new WeakMap();

export default function ({ data, parentElement }) {
    activeTimers.get(parentElement)?.();

    const track = parentElement.querySelector(".subway-track-estimated");
    const train = track.querySelector(".subway-train");
    const countdown = parentElement.querySelector(".subway-countdown");
    const markers = track.querySelectorAll(".subway-stop");
    markers.forEach((marker, index) => {
        marker.classList.toggle("subway-stop-active", index === data.position);
    });

    const start = 12.5 + (data.position ?? 0) * 25;
    const station = 62.5;
    const initial = start + (station - start) * (1 - data.remaining / data.eta);
    const duration = data.remaining * 1000;
    const startedAt = performance.now();
    train.hidden = false;
    train.style.left = `${initial}%`;

    const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    const animation = reduceMotion ? null : train.animate(
        [{ left: `${initial}%` }, { left: `${station}%` }],
        { duration, fill: "forwards" },
    );

    let interval;
    function update() {
        const remaining = Math.ceil((duration - (performance.now() - startedAt)) / 1000);
        if (remaining <= 0) {
            countdown.textContent = "예상 시간 경과 · 도착 확인 중";
            train.hidden = true;
            window.clearInterval(interval);
            return;
        }

        const minutes = Math.floor(remaining / 60);
        const seconds = remaining % 60;
        const time = minutes > 0 ? `${minutes}분 ${seconds}초` : `${seconds}초`;
        countdown.textContent = `예상 위치 · 도착까지 ${time}`;
    }

    interval = window.setInterval(update, 250);
    update();
    const stop = () => {
        window.clearInterval(interval);
        animation?.cancel();
    };
    activeTimers.set(parentElement, stop);
    return stop;
}
