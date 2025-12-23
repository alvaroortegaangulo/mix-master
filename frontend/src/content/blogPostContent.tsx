import type { ReactNode } from "react";

export const blogPostContent: Record<string, ReactNode> = {
  "como-eliminar-dc-offset-en-stems": (
    <>
      <p>
        El DC offset es un problema silencioso: no lo escuchas, pero sí lo sufren
        tus medidores, tus compresores y el headroom total de la mezcla. Si tus
        stems llegan con un desplazamiento constante respecto al cero, el bus de
        mezcla arranca con menos margen y los procesos dinámicos reaccionan de
        forma errática.
      </p>

      <section id="que-es-el-dc-offset" className="scroll-mt-24">
        <h2>Qué es el DC offset</h2>
        <p>
          En audio digital, la señal debería oscilar alrededor de 0. El DC
          offset aparece cuando la forma de onda queda desplazada hacia arriba o
          abajo, como si tuviera un valor medio fijo. Esto puede venir de
          convertidores, plugins mal calibrados, sampleos antiguos o exportaciones
          con errores.
        </p>
        <ul>
          <li>Es energía de muy baja frecuencia (casi 0 Hz).</li>
          <li>No aporta información musical útil.</li>
          <li>Ocupa headroom y altera el comportamiento dinámico.</li>
        </ul>
      </section>

      <section id="por-que-importa" className="scroll-mt-24">
        <h2>Por qué importa en los stems</h2>
        <p>
          Si un stem está desplazado, su pico se acerca antes al techo digital y
          el compresor lo percibe como más fuerte de lo que realmente es. Esto
          tiene varias consecuencias:
        </p>
        <ul>
          <li>Menos headroom global en el bus.</li>
          <li>Compresores y limiters reaccionan de forma agresiva.</li>
          <li>Se reduce la claridad del low-end en el sumatorio.</li>
          <li>Más riesgo de distorsión asimétrica.</li>
        </ul>
        <div className="not-prose my-6 rounded-xl border border-teal-500/20 bg-teal-500/10 p-4">
          <p className="text-sm text-teal-100">
            Regla rápida: si al hacer zoom la forma de onda no está centrada en 0,
            hay un DC offset que deberías corregir antes de mezclar.
          </p>
        </div>
      </section>

      <section id="como-detectarlo" className="scroll-mt-24">
        <h2>Cómo detectarlo rápido</h2>
        <ol>
          <li>Usa un medidor de DC o un analizador que muestre el valor medio.</li>
          <li>Haz zoom en el editor y verifica si la forma de onda está centrada.</li>
          <li>Calcula la media: si no es ~0, hay offset.</li>
        </ol>
        <pre>
          <code>{`dc_offset = mean(signal)
signal_fixed = signal - dc_offset`}</code>
        </pre>
        <p>
          En términos prácticos, un valor mayor a -60 dB suele ser lo bastante
          alto como para justificar corrección. La magnitud exacta depende del
          flujo y del estilo.
        </p>
      </section>

      <section id="como-lo-hace-piroola" className="scroll-mt-24">
        <h2>Cómo lo hace Piroola</h2>
        <p>
          En el pipeline, el análisis <strong>S1_STEM_DC_OFFSET.py</strong> mide
          el DC offset y el pico en dBFS de cada stem. Si supera el límite
          esperado (<code>dc_offset_max_db</code>), el stage
          <strong> S1_STEM_DC_OFFSET.py</strong> corrige la señal restando el
          valor medio en todas las muestras, sin cambiar tu balance ni tu color.
        </p>
        <p>
          Todo ocurre después de normalizar formatos en
          <strong> S0_SESSION_FORMAT</strong> (tus archivos pasan a WAV de forma
          interna), lo que permite analizar y corregir sin inconsistencias de
          sample rate.
        </p>
        <ul>
          <li>Analiza cada stem en mono para estimar el offset real.</li>
          <li>Calcula un umbral y corrige solo si es necesario.</li>
          <li>Reescribe los stems limpios en el trabajo temporal.</li>
        </ul>
      </section>

      <section id="solucion-manual" className="scroll-mt-24">
        <h2>Solución manual segura</h2>
        <p>
          Si prefieres corregirlo antes de subir, hazlo así:
        </p>
        <ol>
          <li>Inserta un plugin de DC offset removal o una EQ con filtro HPF.</li>
          <li>Si usas HPF, empieza en 20 Hz con pendiente suave.</li>
          <li>Comprueba que la forma de onda vuelve al centro.</li>
          <li>Exporta el stem sin normalizar ni limitar.</li>
        </ol>
        <p>
          Evita filtros demasiado agresivos en subgraves si trabajas con 808 o
          bajos muy profundos.
        </p>
      </section>

      <section id="checklist" className="scroll-mt-24">
        <h2>Checklist antes de subir stems</h2>
        <ul>
          <li>Archivos a 24-bit o 32-float, sin dither innecesario.</li>
          <li>Sin clipping visible en los picos.</li>
          <li>Silencios limpios al inicio y final.</li>
          <li>Sin normalizar cada stem de forma individual.</li>
          <li>DC offset corregido o dentro del rango seguro.</li>
        </ul>
      </section>

      <section id="faq" className="scroll-mt-24">
        <h2>Preguntas frecuentes</h2>
        <h3>¿El DC offset se oye?</h3>
        <p>
          Normalmente no, pero sí afecta al headroom y al comportamiento de los
          procesos dinámicos. Por eso es importante corregirlo.
        </p>
        <h3>¿Un high-pass sustituye el DC removal?</h3>
        <p>
          Puede ayudar, pero un DC removal es más preciso y no altera el rango
          audible. Usa HPF solo si no tienes otra opción.
        </p>
        <h3>¿Puedo ignorarlo si es pequeño?</h3>
        <p>
          Si está muy por debajo de -60 dB, suele ser aceptable. Pero en stems
          con mucho subgrave, cualquier margen extra cuenta.
        </p>
      </section>
    </>
  ),
  "compresion-bus-bateria-punch-glue": (
    <>
      <p>
        La compresión de bus de batería es la diferencia entre un kit que suena
        unido y uno que parece una suma de pistas aisladas. Pero si te pasas,
        pierdes transientes, pegada y claridad. Aquí tienes un enfoque técnico y
        reproducible.
      </p>

      <section id="por-que-bus" className="scroll-mt-24">
        <h2>Por qué comprimir el bus de batería</h2>
        <p>
          El bus actúa como un pegamento común. Una ligera compresión unifica la
          batería, controla picos y genera sensación de energía constante sin
          matar el impacto.
        </p>
        <ul>
          <li>Mejora la cohesión entre kick, snare y overheads.</li>
          <li>Reduce picos agresivos sin aplastar el groove.</li>
          <li>Facilita que el bus se asiente con el resto de la mezcla.</li>
        </ul>
      </section>

      <section id="crest-factor" className="scroll-mt-24">
        <h2>Crest factor y dinámica útil</h2>
        <p>
          El crest factor es la diferencia entre el pico y el RMS. Una batería
          con crest muy alto puede sentirse descontrolada; con crest demasiado
          bajo, suena plana. Un rango común para bus de batería está entre 6 y
          10 dB dependiendo del estilo.
        </p>
        <div className="not-prose my-6 rounded-xl border border-violet-500/20 bg-violet-500/10 p-4">
          <p className="text-sm text-violet-100">
            Si tu crest factor supera claramente el rango objetivo, necesitas
            compresión suave de bus para recuperar cohesión.
          </p>
        </div>
      </section>

      <section id="ajustes-base" className="scroll-mt-24">
        <h2>Ajustes base recomendados</h2>
        <ul>
          <li>Ratio: 2:1 a 4:1 (3:1 es un punto sólido).</li>
          <li>Attack: 10-30 ms para conservar transientes.</li>
          <li>Release: 100-200 ms para seguir el groove.</li>
          <li>Ganancia reducida: 1-3 dB en promedio.</li>
        </ul>
        <p>
          Ajusta el threshold hasta que el medidor marque una reducción
          consistente, no solo en picos aislados.
        </p>
      </section>

      <section id="como-lo-hace-piroola" className="scroll-mt-24">
        <h2>Cómo lo hace Piroola</h2>
        <p>
          El análisis <strong>S5_BUS_DYNAMICS_DRUMS.py</strong> identifica los
          stems de la familia Drums en tu sesión y calcula el crest factor del
          bus. Si el valor supera el objetivo, el stage de dinámica aplica una
          compresión de glue con envolvente común para todo el bus.
        </p>
        <p>
          En producción, usamos un detector de picos con ratio 3:1, attack 10 ms
          y release 150 ms. El algoritmo calcula el threshold en función del
          crest factor y limita la reducción media (<code>max_average_gain_reduction_db</code>)
          para no destruir los transientes.
        </p>
        <ul>
          <li>Construye un bus multicanal con todos los stems de batería.</li>
          <li>Aplica la misma envolvente a todos los canales.</li>
          <li>Reescribe los stems con la compresión aplicada.</li>
          <li>Guarda métricas pre/post en un JSON de control.</li>
        </ul>
      </section>

      <section id="paso-a-paso" className="scroll-mt-24">
        <h2>Paso a paso manual</h2>
        <ol>
          <li>Rutea kick, snare, toms y OH a un bus dedicado.</li>
          <li>Inserta un compresor con ratio 3:1 y attack 10 ms.</li>
          <li>Reduce 1-3 dB en los picos fuertes.</li>
          <li>Ajusta el release para que respire con el tempo.</li>
          <li>Si falta punch, sube el attack o baja el ratio.</li>
        </ol>
        <p>
          Si necesitas más densidad sin perder pegada, usa compresión paralela y
          mezcla el bus comprimido al gusto.
        </p>
      </section>

      <section id="errores-comunes" className="scroll-mt-24">
        <h2>Errores comunes</h2>
        <ul>
          <li>Attack demasiado rápido: aplana transientes y quita pegada.</li>
          <li>Release demasiado corto: bombeo audible.</li>
          <li>Más de 4 dB de reducción media: batería sin vida.</li>
          <li>Compresión sin escuchar el low-end: el kick pierde definición.</li>
        </ul>
      </section>

      <section id="checklist" className="scroll-mt-24">
        <h2>Checklist rápido</h2>
        <ul>
          <li>GR media entre 1-3 dB.</li>
          <li>Crest factor dentro del rango objetivo.</li>
          <li>Transientes del kick y snare siguen presentes.</li>
          <li>No hay bombeo en hi-hats u overheads.</li>
        </ul>
      </section>
    </>
  ),
};
