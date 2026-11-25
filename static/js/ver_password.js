(function () {
    var OCULTO = "••••••••";
    var SEGUNDOS_VISIBLE = 15;

    function escribir(destino, texto) {
        if (destino.tagName === "INPUT") {
            destino.value = texto;
        } else {
            destino.textContent = texto;
        }
    }

    function ocultar(boton, destino) {
        clearTimeout(boton._temporizador);
        escribir(destino, OCULTO);
        boton.dataset.visible = "";
        boton.firstElementChild.className = "bi bi-eye";
    }

    document.addEventListener("click", function (evento) {
        var boton = evento.target.closest("[data-revelar-url]");
        if (!boton) return;
        var destino = boton.parentElement.querySelector(".pass-valor");
        if (!destino) return;

        if (boton.dataset.visible) {
            ocultar(boton, destino);
            return;
        }

        boton.disabled = true;
        fetch(boton.dataset.revelarUrl, {
            method: "POST",
            credentials: "same-origin",
            headers: {
                "X-CSRFToken": boton.dataset.csrf,
                "X-Requested-With": "XMLHttpRequest"
            }
        })
            .then(function (respuesta) {
                return respuesta.json().then(function (datos) {
                    return { ok: respuesta.ok, datos: datos };
                });
            })
            .then(function (resultado) {
                if (!resultado.ok) {
                    escribir(destino, resultado.datos.error || "No disponible");
                    boton._temporizador = setTimeout(function () {
                        ocultar(boton, destino);
                    }, 2500);
                    return;
                }
                escribir(destino, resultado.datos.password);
                boton.dataset.visible = "1";
                boton.firstElementChild.className = "bi bi-eye-slash";
                boton._temporizador = setTimeout(function () {
                    ocultar(boton, destino);
                }, SEGUNDOS_VISIBLE * 1000);
            })
            .catch(function () {
                escribir(destino, "Error de conexión");
                boton._temporizador = setTimeout(function () {
                    ocultar(boton, destino);
                }, 2500);
            })
            .finally(function () {
                boton.disabled = false;
            });
    });
})();