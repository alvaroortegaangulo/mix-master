import type { ReactNode } from "react";
import { BlogLocale, defaultBlogLocale } from "./blogPosts";
import BlogCallout from "../components/blog/BlogCallout";
import BlogChecklist from "../components/blog/BlogChecklist";
import BlogAudioPlayer from "../components/blog/BlogAudioPlayer";

export const blogPostContent: Record<BlogLocale, Record<string, ReactNode>> = {
  es: {
    "como-eliminar-dc-offset-en-stems": (
      <>
        <p>
          El DC offset es un problema silencioso: no lo escuchas, pero sí lo
          sufren tus medidores, tus compresores y el headroom total de la mezcla.
          Si tus stems llegan con un desplazamiento constante respecto al cero,
          el bus de mezcla arranca con menos margen y los procesos dinámicos
          reaccionan de forma errática.
        </p>

        <section id="que-es-el-dc-offset" className="scroll-mt-24">
          <h2>Qué es el DC offset</h2>
          <p>
            En audio digital, la señal debería oscilar alrededor de 0. El DC
            offset aparece cuando la forma de onda queda desplazada hacia arriba
            o abajo, como si tuviera un valor medio fijo. Esto puede venir de
            convertidores, plugins mal calibrados, sampleos antiguos o
            exportaciones con errores.
          </p>
          <BlogCallout type="concept" title="Concepto Clave">
            El DC Offset es energía de frecuencia 0 Hz. No suena, pero "empuja"
            la señal hacia el techo digital, robando headroom invisiblemente.
          </BlogCallout>
        </section>

        <section id="por-que-importa" className="scroll-mt-24">
          <h2>Por qué importa en los stems</h2>
          <p>
            Si un stem está desplazado, su pico se acerca antes al techo digital
            y el compresor lo percibe como más fuerte de lo que realmente es.
            Esto tiene varias consecuencias:
          </p>
          <ul>
            <li>Menos headroom global en el bus.</li>
            <li>Compresores y limiters reaccionan de forma agresiva.</li>
            <li>Se reduce la claridad del low-end en el sumatorio.</li>
            <li>Más riesgo de distorsión asimétrica.</li>
          </ul>
          <BlogCallout type="tip" title="Regla de Oro">
            Si al hacer zoom máximo en tu DAW la línea de silencio no está perfectamente
            centrada en el eje 0, tienes DC Offset. Corrígelo antes de empezar a mezclar.
          </BlogCallout>
        </section>

        <section id="como-detectarlo" className="scroll-mt-24">
          <h2>Cómo detectarlo rápido</h2>
          <p>
            En términos prácticos, un valor mayor a -60 dB suele ser lo bastante
            alto como para justificar corrección. La magnitud exacta depende del
            flujo y del estilo.
          </p>
          <pre>
            <code>{`// Pseudocódigo de detección
dc_offset = mean(signal)
if abs(dc_offset) > threshold:
    signal_fixed = signal - dc_offset`}</code>
          </pre>
        </section>

        <section id="como-lo-hace-piroola" className="scroll-mt-24">
          <h2>Cómo lo hace Piroola</h2>
          <p>
            En el pipeline, el análisis <strong>S1_STEM_DC_OFFSET.py</strong>
            mide el DC offset y el pico en dBFS de cada stem. Si supera el límite
            esperado, el sistema corrige la señal restando el valor medio
            matemático.
          </p>
          <BlogAudioPlayer
            title="Corrección de DC Offset (Simulación)"
            labelBefore="Original (Offset)"
            labelAfter="Corregido (Centrado)"
          />
        </section>

        <section id="solucion-manual" className="scroll-mt-24">
          <h2>Solución manual segura</h2>
          <p>Si prefieres corregirlo antes de subir, hazlo así:</p>
          <ol>
            <li>Inserta un plugin de DC offset removal o una EQ con filtro HPF.</li>
            <li>Si usas HPF, empieza en 20 Hz con pendiente suave.</li>
            <li>Comprueba que la forma de onda vuelve al centro.</li>
            <li>Exporta el stem sin normalizar ni limitar.</li>
          </ol>
          <BlogCallout type="warning" title="Cuidado con los Subgraves">
             Evita usar filtros High-Pass agresivos (por encima de 30Hz) en bombos tipo 808
             para quitar el DC Offset, ya que podrías alterar la fase y el peso del grave.
             Usa herramientas dedicadas de "DC Removal" siempre que sea posible.
          </BlogCallout>
        </section>

        <section id="checklist" className="scroll-mt-24">
          <BlogChecklist
            title="Checklist de Limpieza de Stems"
            items={[
              "Archivos a 24-bit o 32-float para mantener el rango dinámico.",
              "Sin clipping visible (picos por debajo de 0 dBFS).",
              "Silencios limpios al inicio y final (fades cortos).",
              "Sin normalizar cada stem individualmente (conserva el balance).",
              "DC offset corregido o verificado por debajo de -60dB."
            ]}
          />
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
        </section>
      </>
    ),
    "compresion-bus-bateria-punch-glue": (
      <>
        <p>
          La compresión de bus de batería es la diferencia entre un kit que suena
          unido y uno que parece una suma de pistas aisladas. Pero si te pasas,
          pierdes transientes, pegada y claridad. Aquí tienes un enfoque técnico
          y reproducible.
        </p>

        <section id="por-que-bus" className="scroll-mt-24">
          <h2>El concepto de "Glue" (Pegamento)</h2>
          <p>
            El bus actúa como un pegamento común. Una ligera compresión unifica la
            batería, controla picos y genera sensación de energía constante sin
            matar el impacto.
          </p>
          <BlogCallout type="info" title="Glue Compression">
             La compresión de "pegamento" se caracteriza por un ataque lento (para dejar pasar el golpe)
             y un release rápido o automático (para volver a tiempo antes del siguiente golpe),
             con ratios bajos (2:1 o 4:1).
          </BlogCallout>
        </section>

        <section id="crest-factor" className="scroll-mt-24">
          <h2>Crest factor y dinámica útil</h2>
          <p>
            El crest factor es la diferencia entre el pico y el RMS. Una batería
            con crest muy alto puede sentirse descontrolada; con crest demasiado
            bajo, suena plana. Un rango común para bus de batería está entre 6 y
            10 dB dependiendo del estilo.
          </p>
        </section>

        <section id="ajustes-base" className="scroll-mt-24">
          <h2>Ajustes base recomendados</h2>
          <BlogChecklist
            title="Configuración de Compresor Bus"
            items={[
               "Ratio: 2:1 a 4:1 (3:1 es el punto dulce).",
               "Attack: 10-30 ms (vital para conservar transientes).",
               "Release: 100-200 ms (ajustar al tempo/groove).",
               "Gain Reduction: 1-3 dB máximo en medidores."
            ]}
          />
          <p className="mt-4">
            Ajusta el threshold hasta que el medidor marque una reducción
            consistente, no solo en picos aislados.
          </p>
        </section>

        <section id="como-lo-hace-piroola" className="scroll-mt-24">
          <h2>Cómo lo hace Piroola</h2>
          <p>
            El análisis <strong>S5_BUS_DYNAMICS_DRUMS.py</strong> identifica los
            stems de la familia Drums y calcula el crest factor. Si es necesario,
            aplica compresión inteligente.
          </p>
          <BlogAudioPlayer
            title="Compresión de Bus (Glue)"
            labelBefore="Dry (Sin Compresión)"
            labelAfter="Wet (Con Glue)"
          />
        </section>

        <section id="paso-a-paso" className="scroll-mt-24">
          <h2>Paso a paso manual</h2>
          <ol>
            <li>Rutea kick, snare, toms y OH a un bus dedicado.</li>
            <li>Inserta un compresor tipo SSL o VCA.</li>
            <li>Reduce 1-3 dB en los picos fuertes.</li>
            <li>Ajusta el release para que la aguja "baile" con el tempo.</li>
          </ol>
          <BlogCallout type="tip" title="Compresión Paralela">
             Si necesitas más densidad sin perder la pegada de los transientes originales,
             duplica el bus, comprime uno agresivamente (10dB GR, ataque rápido) y mézclalo
             sutilmente por debajo del bus original limpio.
          </BlogCallout>
        </section>

        <section id="errores-comunes" className="scroll-mt-24">
          <h2>Errores comunes</h2>
          <ul>
            <li>Attack demasiado rápido: aplana transientes y quita pegada.</li>
            <li>Release demasiado corto: bombeo audible (distorsión en graves).</li>
            <li>Más de 4 dB de reducción media: batería sin vida.</li>
          </ul>
        </section>
      </>
    ),
    "alineacion-fase-bateria-multimic": (
      <>
        <p>
          Cuando grabas una batería con varios micrófonos, cualquier diferencia de
          tiempo o polaridad puede provocar cancelaciones. Eso se traduce en un
          kick débil, una caja hueca o un estéreo borroso.
        </p>

        <section id="sintomas-fase" className="scroll-mt-24">
          <h2>Síntomas de fase</h2>
          <BlogChecklist
             title="Síntomas de Mala Fase"
             items={[
               "El low-end desaparece al sumar overheads con el bombo.",
               "La caja suena delgada o hueca al activar los room mics.",
               "El sonido mejora paradójicamente cuando pones la mezcla en MONO.",
               "El medidor de correlación marca valores negativos (hacia -1)."
             ]}
          />
        </section>

        <section id="por-que-se-pierde" className="scroll-mt-24">
          <h2>Por qué se pierde la fase</h2>
          <p>
            Cada micrófono está a una distancia distinta del parche. El sonido viaja
            a ~343 m/s, por lo que cada milisegundo cuenta.
          </p>
          <BlogCallout type="concept" title="Física del Sonido">
             1 ms de retraso equivale a unos 34 cm de distancia. Si tus overheads están
             a 1 metro más de la caja que el micro cercano, el sonido llegará casi 3ms tarde,
             creando un filtro de peine (comb filtering) audible.
          </BlogCallout>
        </section>

        <section id="como-medir" className="scroll-mt-24">
          <h2>Cómo medir y alinear</h2>
          <ol>
            <li>Escucha en mono y detecta qué pistas se cancelan.</li>
            <li>Prueba inversión de polaridad (botón Ø) en kick o snare.</li>
            <li>Alinea por muestras (nudge) en tu DAW.</li>
          </ol>
        </section>

        <section id="como-lo-hace-piroola" className="scroll-mt-24">
          <h2>Cómo lo hace Piroola</h2>
          <p>
            El análisis <strong>S2_GROUP_PHASE_DRUMS.py</strong> identifica los
            stems de batería y calcula su correlación cruzada. El sistema
            alinea temporalmente los micros para maximizar el impacto.
          </p>
          <BlogAudioPlayer
             title="Alineación de Fase"
             labelBefore="Desfasado (Débil)"
             labelAfter="Alineado (Sólido)"
          />
        </section>

        <section id="checklist" className="scroll-mt-24">
          <BlogCallout type="tip" title="Tip de Producción">
             Alinea siempre la fase de los Overheads respecto a la Caja (Snare).
             La caja es el elemento central que conecta los micros cercanos con el sonido de sala.
          </BlogCallout>
        </section>
      </>
    ),
    "control-resonancias-stems": (
      <>
        <p>
          Las resonancias son picos estreitos que sobresalen y hacen que una pista
          suene áspera o nasal. No se arreglan con una EQ global: necesitan cortes
          quirúrgicos.
        </p>

        <section id="que-son-resonancias" className="scroll-mt-24">
          <h2>Qué son las resonancias</h2>
          <p>
            Son acumulaciones de energía en bandas muy concretas, causadas por la
            sala, el instrumento o el micrófono.
          </p>
        </section>

        <section id="por-que-problema" className="scroll-mt-24">
          <h2>Por qué son un problema</h2>
          <BlogChecklist
             title="Problemas de Resonancia"
             items={[
               "Fatigan el oído rápidamente (efecto 'silbido').",
               "Enmascaran la inteligibilidad de las voces.",
               "Disparan compresores innecesariamente en frecuencias específicas.",
               "Obligan a bajar el volumen general de la pista."
             ]}
          />
        </section>

        <section id="como-detectar" className="scroll-mt-24">
          <h2>Cómo detectarlas</h2>
          <p>La técnica del barrido es infalible:</p>
          <ol>
            <li>Usa un EQ paramétrico con Q muy alto (estrecho).</li>
            <li>Sube la ganancia +10dB.</li>
            <li>Barre lentamente el espectro hasta que el sonido "pite" o moleste mucho.</li>
            <li>Ahí tienes tu frecuencia resonante. Ahora baja la ganancia a -3dB o -5dB.</li>
          </ol>
        </section>

        <section id="como-lo-hace-piroola" className="scroll-mt-24">
          <h2>Cómo lo hace Piroola</h2>
          <p>
            El stage <strong>S4_STEM_RESONANCE_CONTROL.py</strong> detecta
            picos estáticos y aplica filtros notch quirúrgicos.
          </p>
          <BlogAudioPlayer
             title="Limpieza Espectral"
             labelBefore="Original (Áspero)"
             labelAfter="Limpio (Suave)"
          />
        </section>

        <section id="checklist" className="scroll-mt-24">
          <BlogCallout type="warning" title="No Te Pases">
             Es fácil emocionarse y cortar demasiadas frecuencias, dejando el sonido "hueco" o sin vida.
             Corta solo lo que realmente moleste y comprueba siempre en contexto con la mezcla completa.
          </BlogCallout>
        </section>
      </>
    ),
    "lufs-true-peak-loudness": (
      <>
        <p>
          Llegar al loudness es fácil si limitas demasiado, pero el resultado suele
          sonar plano. La clave es entender LUFS y true peak.
        </p>

        <section id="que-son-lufs" className="scroll-mt-24">
          <h2>Qué son los LUFS</h2>
          <BlogCallout type="concept" title="LUFS vs RMS">
            RMS mide la potencia eléctrica media. LUFS mide la sonoridad percibida por el oído humano,
            teniendo en cuenta que escuchamos los medios más fuerte que los graves.
          </BlogCallout>
        </section>

        <section id="targets-streaming" className="scroll-mt-24">
          <h2>Targets de streaming</h2>
          <p>
            Muchas plataformas normalizan alrededor de -14 LUFS.
          </p>
          <BlogChecklist
             title="Estándares de la Industria"
             items={[
               "Spotify/YouTube: Normalizan a -14 LUFS.",
               "Apple Music: Alrededor de -16 LUFS.",
               "Club/CD Master: Suelen ir de -9 a -6 LUFS (más fuerte).",
               "True Peak: Siempre dejar margen (-1.0 dBTP para streaming)."
             ]}
          />
        </section>

        <section id="true-peak" className="scroll-mt-24">
          <h2>True peak e intersample peaks</h2>
          <p>
            Los intersample peaks aparecen cuando la reconstrucción analógica supera
            el 0 dBFS aunque el archivo digital no clippee.
          </p>
          <BlogCallout type="tip" title="El Margen de Seguridad">
             Si masterizas a -0.1 dBTP, al convertir a MP3/AAC para streaming es casi seguro
             que generarás distorsión por la compresión con pérdidas. Usa -1.0 dBTP para estar seguro.
          </BlogCallout>
        </section>

        <section id="como-lo-hace-piroola" className="scroll-mt-24">
          <h2>Cómo lo hace Piroola</h2>
          <p>
            <strong>S10_MASTER_FINAL_LIMITS.py</strong> verifica LUFS, true peak y
            correlación para ajustar micro‑ganancias sin perder dinámica.
          </p>
          <BlogAudioPlayer
             title="Limitación Final"
             labelBefore="Mezcla (-18 LUFS)"
             labelAfter="Master (-9 LUFS)"
          />
        </section>
      </>
    ),
  },
  en: {
    "como-eliminar-dc-offset-en-stems": (
      <>
        <p>
          DC offset is a silent issue: you do not hear it, but your meters,
          compressors, and overall headroom do. When stems arrive with a constant
          shift around zero, the mix bus starts with less margin and dynamic
          processors react in an unstable way.
        </p>

        <section id="que-es-el-dc-offset" className="scroll-mt-24">
          <h2>What is DC offset</h2>
          <p>
            In digital audio, the waveform should oscillate around 0. DC offset
            appears when the waveform is shifted up or down as if it had a fixed
            average value. It can come from converters, miscalibrated plugins,
            old samples, or bad exports.
          </p>
          <ul>
            <li>It is extremely low-frequency energy (near 0 Hz).</li>
            <li>It carries no useful musical information.</li>
            <li>It eats headroom and changes dynamic behavior.</li>
          </ul>
        </section>

        <section id="por-que-importa" className="scroll-mt-24">
          <h2>Why it matters on stems</h2>
          <p>
            If a stem is offset, peaks hit the digital ceiling earlier and the
            compressor interprets the signal as louder than it really is. That
            leads to:
          </p>
          <ul>
            <li>Less headroom on the mix bus.</li>
            <li>Aggressive compressor and limiter behavior.</li>
            <li>Muddier low-end in the sum.</li>
            <li>Higher risk of asymmetric distortion.</li>
          </ul>
          <div className="not-prose my-6 rounded-xl border border-teal-500/20 bg-teal-500/10 p-4">
            <p className="text-sm text-teal-100">
              Quick rule: if the waveform is not centered at 0 when you zoom in,
              you should remove DC offset before mixing.
            </p>
          </div>
        </section>

        <section id="como-detectarlo" className="scroll-mt-24">
          <h2>How to detect it quickly</h2>
          <ol>
            <li>Use a DC meter or analyzer that shows the average value.</li>
            <li>Zoom in and check if the waveform is centered.</li>
            <li>Compute the mean: if it is not ~0, there is offset.</li>
          </ol>
          <pre>
            <code>{`dc_offset = mean(signal)
signal_fixed = signal - dc_offset`}</code>
          </pre>
          <p>
            In practice, values higher than -60 dB are often worth correcting.
            Exact thresholds depend on style and workflow.
          </p>
        </section>

        <section id="como-lo-hace-piroola" className="scroll-mt-24">
          <h2>How Piroola handles it</h2>
          <p>
            In the pipeline, <strong>S1_STEM_DC_OFFSET.py</strong> measures DC
            offset and peak dBFS for each stem. If it exceeds the expected limit
            (<code>dc_offset_max_db</code>), the stage
            <strong> S1_STEM_DC_OFFSET.py</strong> subtracts the mean value from
            all samples without changing balance or tone.
          </p>
          <p>
            This happens after format normalization in
            <strong> S0_SESSION_FORMAT</strong> (files are converted to WAV
            internally), so the analysis is consistent across sample rates.
          </p>
          <ul>
            <li>Analyze each stem in mono to estimate the real offset.</li>
            <li>Compute a threshold and correct only when needed.</li>
            <li>Rewrite clean stems in the temp workspace.</li>
          </ul>
        </section>

        <section id="solucion-manual" className="scroll-mt-24">
          <h2>Safe manual fix</h2>
          <p>If you prefer to fix it before upload:</p>
          <ol>
            <li>Insert a DC offset removal plugin or an EQ with HPF.</li>
            <li>If using HPF, start around 20 Hz with a gentle slope.</li>
            <li>Check that the waveform is centered again.</li>
            <li>Export the stem without normalization or limiting.</li>
          </ol>
          <p>
            Avoid aggressive filters if you work with deep sub‑bass or 808s.
          </p>
        </section>

        <section id="checklist" className="scroll-mt-24">
          <h2>Checklist before uploading stems</h2>
          <ul>
            <li>24-bit or 32-float files, no unnecessary dither.</li>
            <li>No visible clipping on peaks.</li>
            <li>Clean silence at start and end.</li>
            <li>No per-stem normalization.</li>
            <li>DC offset corrected or within safe range.</li>
          </ul>
        </section>

        <section id="faq" className="scroll-mt-24">
          <h2>FAQs</h2>
          <h3>Can you hear DC offset?</h3>
          <p>
            Usually no, but it affects headroom and dynamic processors. That is
            why it matters.
          </p>
          <h3>Does a high‑pass filter replace DC removal?</h3>
          <p>
            It can help, but DC removal is more precise and does not alter the
            audible band. Use HPF only if needed.
          </p>
          <h3>Can I ignore small offsets?</h3>
          <p>
            If it is far below -60 dB, it is often acceptable. But with heavy
            sub content, every bit of headroom counts.
          </p>
        </section>
      </>
    ),
    "compresion-bus-bateria-punch-glue": (
      <>
        <p>
          Drum bus compression is the difference between a kit that feels glued
          together and a pile of isolated tracks. Overdo it and you lose
          transients, punch, and clarity. This is a technical, repeatable
          approach.
        </p>

        <section id="por-que-bus" className="scroll-mt-24">
          <h2>Why compress the drum bus</h2>
          <p>
            The bus acts as glue. A light compressor unifies the kit, controls
            peaks, and keeps energy consistent without killing impact.
          </p>
          <ul>
            <li>Improves cohesion between kick, snare, and overheads.</li>
            <li>Tames aggressive peaks without flattening the groove.</li>
            <li>Helps the drums sit with the rest of the mix.</li>
          </ul>
        </section>

        <section id="crest-factor" className="scroll-mt-24">
          <h2>Crest factor and useful dynamics</h2>
          <p>
            Crest factor is the difference between peak and RMS. Too high feels
            wild; too low feels flat. A common drum‑bus range is 6‑10 dB,
            depending on style.
          </p>
          <div className="not-prose my-6 rounded-xl border border-violet-500/20 bg-violet-500/10 p-4">
            <p className="text-sm text-violet-100">
              If your crest factor is clearly above target, gentle bus
              compression brings cohesion back.
            </p>
          </div>
        </section>

        <section id="ajustes-base" className="scroll-mt-24">
          <h2>Recommended base settings</h2>
          <ul>
            <li>Ratio: 2:1 to 4:1 (3:1 is a strong starting point).</li>
            <li>Attack: 10‑30 ms to keep transients.</li>
            <li>Release: 100‑200 ms to follow the groove.</li>
            <li>Gain reduction: 1‑3 dB on average.</li>
          </ul>
          <p>
            Set the threshold so the meter shows consistent reduction, not just
            on isolated peaks.
          </p>
        </section>

        <section id="como-lo-hace-piroola" className="scroll-mt-24">
          <h2>How Piroola does it</h2>
          <p>
            <strong>S5_BUS_DYNAMICS_DRUMS.py</strong> identifies drum stems and
            computes the bus crest factor. If it exceeds target, the dynamics
            stage applies glue compression with a shared envelope for the entire
            bus.
          </p>
          <p>
            In production we use a peak detector with ratio 3:1, 10 ms attack
            and 150 ms release. The algorithm calculates threshold from crest
            factor and caps average reduction (
            <code>max_average_gain_reduction_db</code>) to preserve transients.
          </p>
          <ul>
            <li>Builds a multichannel bus from all drum stems.</li>
            <li>Applies one envelope to all channels.</li>
            <li>Rewrites stems with bus compression applied.</li>
            <li>Saves pre/post metrics for reporting.</li>
          </ul>
        </section>

        <section id="paso-a-paso" className="scroll-mt-24">
          <h2>Manual step‑by‑step</h2>
          <ol>
            <li>Route kick, snare, toms, and OH to a dedicated bus.</li>
            <li>Insert a compressor at 3:1 with 10 ms attack.</li>
            <li>Reduce 1‑3 dB on stronger hits.</li>
            <li>Adjust release to breathe with tempo.</li>
            <li>If punch is missing, raise attack or lower ratio.</li>
          </ol>
          <p>
            If you need more density without losing impact, use parallel
            compression and blend to taste.
          </p>
        </section>

        <section id="errores-comunes" className="scroll-mt-24">
          <h2>Common mistakes</h2>
          <ul>
            <li>Attack too fast: transients collapse.</li>
            <li>Release too short: audible pumping.</li>
            <li>More than 4 dB average reduction: lifeless drums.</li>
            <li>Ignoring low‑end: kick loses definition.</li>
          </ul>
        </section>

        <section id="checklist" className="scroll-mt-24">
          <h2>Quick checklist</h2>
          <ul>
            <li>Average GR between 1‑3 dB.</li>
            <li>Crest factor within target range.</li>
            <li>Kick and snare transients stay present.</li>
            <li>No pumping on hats or overheads.</li>
          </ul>
        </section>
      </>
    ),
    "alineacion-fase-bateria-multimic": (
      <>
        <p>
          Multi‑mic drum recordings can suffer phase cancellation when timing or
          polarity is off. That usually means weak kick, hollow snare, or blurry
          stereo. Here is a practical way to align phase without losing punch.
        </p>

        <section id="sintomas-fase" className="scroll-mt-24">
          <h2>Symptoms of phase issues</h2>
          <ul>
            <li>Low‑end disappears when overheads are added.</li>
            <li>Snare loses body when room mics are on.</li>
            <li>The mix sounds better in mono.</li>
            <li>Correlation meter drops into negative values.</li>
          </ul>
        </section>

        <section id="por-que-se-pierde" className="scroll-mt-24">
          <h2>Why phase shifts happen</h2>
          <p>
            Each mic sits at a different distance from the drum head. That
            timing difference shifts phase and changes the sum. Polarity flips
            or un‑compensated latency can make it worse.
          </p>
          <ul>
            <li>Distance differences between microphones.</li>
            <li>Polarity inversion in preamps or plugins.</li>
            <li>Latency from external processing.</li>
          </ul>
        </section>

        <section id="como-medir" className="scroll-mt-24">
          <h2>How to measure and align</h2>
          <ol>
            <li>Listen in mono and identify the cancellations.</li>
            <li>Use a correlation meter to see the phase offset.</li>
            <li>Try polarity inversion on kick or snare.</li>
            <li>Nudge samples until low‑end and punch return.</li>
          </ol>
        </section>

        <section id="como-lo-hace-piroola" className="scroll-mt-24">
          <h2>How Piroola handles it</h2>
          <p>
            <strong>S2_GROUP_PHASE_DRUMS.py</strong> analyzes drum stems and
            computes correlation. The stage applies time alignment and polarity
            correction to maximize drum‑bus coherence without changing balance.
          </p>
          <ul>
            <li>Detects problematic pairs in kick, snare, and overheads.</li>
            <li>Applies sample‑level offsets.</li>
            <li>Validates coherence with phase metrics.</li>
          </ul>
        </section>

        <section id="paso-a-paso" className="scroll-mt-24">
          <h2>Manual workflow</h2>
          <ol>
            <li>Check kick + overheads in mono.</li>
            <li>Flip polarity where low‑end collapses.</li>
            <li>Align main transients in a sample editor.</li>
            <li>Repeat with snare and room mics.</li>
          </ol>
        </section>

        <section id="errores-comunes" className="scroll-mt-24">
          <h2>Common mistakes</h2>
          <ul>
            <li>Trusting waveforms over your ears.</li>
            <li>Aligning everything to the same point without groove context.</li>
            <li>Forgetting polarity checks before nudging.</li>
          </ul>
        </section>

        <section id="checklist" className="scroll-mt-24">
          <h2>Checklist</h2>
          <ul>
            <li>Stable, positive correlation.</li>
            <li>Solid low‑end in mono.</li>
            <li>Clear transients without flanging artifacts.</li>
          </ul>
        </section>
      </>
    ),
    "control-resonancias-stems": (
      <>
        <p>
          Resonances are narrow peaks that stick out and make a track sound harsh
          or nasal. They cannot be fixed with broad EQ moves; you need surgical
          cuts that keep the original tone intact.
        </p>

        <section id="que-son-resonancias" className="scroll-mt-24">
          <h2>What resonances are</h2>
          <p>
            They are energy buildups in very specific bands caused by the room,
            the instrument, or the microphone. When stems stack up, those
            frequencies become fatiguing.
          </p>
        </section>

        <section id="por-que-problema" className="scroll-mt-24">
          <h2>Why they are a problem</h2>
          <ul>
            <li>They tire the ear in long listening sessions.</li>
            <li>They mask vocals and key elements.</li>
            <li>They force you to turn the mix down.</li>
          </ul>
        </section>

        <section id="como-detectar" className="scroll-mt-24">
          <h2>How to detect them</h2>
          <ol>
            <li>Use an analyzer and find narrow peaks.</li>
            <li>Sweep with a parametric EQ at high Q.</li>
            <li>Confirm the peak is persistent, not a single hit.</li>
          </ol>
        </section>

        <section id="como-lo-hace-piroola" className="scroll-mt-24">
          <h2>How Piroola does it</h2>
          <p>
            <strong>S4_STEM_RESONANCE_CONTROL.py</strong> detects persistent
            resonances and applies gentle reductions per band. Then
            <strong> S4_STEM_HPF_LPF.py</strong> cleans the extremes to leave
            space for the rest of the mix.
          </p>
          <ul>
            <li>Finds narrow peaks per stem.</li>
            <li>Applies small cuts with high Q.</li>
            <li>Protects the core tone.</li>
          </ul>
        </section>

        <section id="workflow-manual" className="scroll-mt-24">
          <h2>Manual workflow</h2>
          <ol>
            <li>Insert a parametric EQ before compression.</li>
            <li>Boost and sweep with +6 dB and high Q.</li>
            <li>Cut 2‑4 dB on each detected peak.</li>
            <li>If it is intermittent, use dynamic EQ.</li>
          </ol>
        </section>

        <section id="errores-comunes" className="scroll-mt-24">
          <h2>Common mistakes</h2>
          <ul>
            <li>Over‑wide cuts that thin the sound.</li>
            <li>Removing resonances that define character.</li>
            <li>Correcting after compression and making it worse.</li>
          </ul>
        </section>

        <section id="checklist" className="scroll-mt-24">
          <h2>Checklist</h2>
          <ul>
            <li>Less harshness without losing presence.</li>
            <li>Narrow, controlled cuts.</li>
            <li>Dynamics intact before compression.</li>
          </ul>
        </section>
      </>
    ),
    "lufs-true-peak-loudness": (
      <>
        <p>
          Hitting loudness is easy if you over‑limit, but the mix will sound
          flat. The key is understanding LUFS and true peak so you can push
          volume without destroying dynamics.
        </p>

        <section id="que-son-lufs" className="scroll-mt-24">
          <h2>What LUFS actually means</h2>
          <p>
            LUFS measure perceived loudness. Integrated LUFS covers the whole
            track, while short‑term shows local changes. The goal is consistent
            loudness without crushing transients.
          </p>
        </section>

        <section id="targets-streaming" className="scroll-mt-24">
          <h2>Streaming targets</h2>
          <p>
            Many platforms normalize around -14 LUFS integrated and recommend
            -1 dBTP true peak. It is not a hard rule: genre and intent matter.
          </p>
          <ul>
            <li>-14 LUFS is a common reference, not a mandate.</li>
            <li>-1 dBTP helps prevent codec distortion.</li>
            <li>Always compare within your genre.</li>
          </ul>
        </section>

        <section id="true-peak" className="scroll-mt-24">
          <h2>True peak and intersample peaks</h2>
          <p>
            Intersample peaks happen when the reconstructed analog waveform
            exceeds 0 dBFS even if the digital samples do not clip. That is why
            true peak control is essential in mastering.
          </p>
        </section>

        <section id="como-lo-hace-piroola" className="scroll-mt-24">
          <h2>How Piroola handles it</h2>
          <p>
            <strong>S9_MASTER_GENERIC.py</strong> prepares final limiting and
            <strong> S10_MASTER_FINAL_LIMITS.py</strong> checks LUFS, true peak,
            and correlation to apply micro‑adjustments without killing dynamics.
          </p>
          <ul>
            <li>Applies gentle limiting with a safe ceiling.</li>
            <li>Verifies integrated LUFS and final true peak.</li>
            <li>Stores metrics for the technical report.</li>
          </ul>
        </section>

        <section id="paso-a-paso" className="scroll-mt-24">
          <h2>Manual step‑by‑step</h2>
          <ol>
            <li>Measure LUFS and true peak on your mix.</li>
            <li>Set limiter ceiling between -1 and -0.5 dBTP.</li>
            <li>Lower threshold until you reach the target LUFS.</li>
            <li>Listen for pumping or distortion.</li>
          </ol>
        </section>

        <section id="errores-comunes" className="scroll-mt-24">
          <h2>Common mistakes</h2>
          <ul>
            <li>Over‑limiting and losing transients.</li>
            <li>Ignoring true peak and clipping in encoding.</li>
            <li>Forcing a target that does not fit the genre.</li>
          </ul>
        </section>

        <section id="checklist" className="scroll-mt-24">
          <h2>Checklist</h2>
          <ul>
            <li>Integrated LUFS in the desired range.</li>
            <li>True peak below the safety ceiling.</li>
            <li>Dynamics and punch preserved.</li>
          </ul>
        </section>
      </>
    ),
  },
  fr: {
    "como-eliminar-dc-offset-en-stems": (
      <>
        <p>
          Le DC offset est un problème silencieux : on ne l’entend pas, mais les
          mètres, les compresseurs et le headroom total le subissent. Si vos
          stems arrivent avec un décalage constant par rapport à zéro, le bus de
          mix démarre avec moins de marge et les traitements dynamiques réagissent
          mal.
        </p>

        <section id="que-es-el-dc-offset" className="scroll-mt-24">
          <h2>Qu’est-ce que le DC offset</h2>
          <p>
            En audio numérique, l’onde devrait osciller autour de 0. Le DC offset
            apparaît quand la forme d’onde est déplacée vers le haut ou le bas,
            comme si elle avait une moyenne fixe. Cela peut venir des
            convertisseurs, de plugins mal calibrés, d’échantillons anciens ou
            d’exports incorrects.
          </p>
          <ul>
            <li>Énergie très basse fréquence (proche de 0 Hz).</li>
            <li>Pas d’information musicale utile.</li>
            <li>Réduit le headroom et perturbe la dynamique.</li>
          </ul>
        </section>

        <section id="por-que-importa" className="scroll-mt-24">
          <h2>Pourquoi c’est important</h2>
          <p>
            Un stem décalé atteint plus vite le plafond numérique et le
            compresseur le perçoit comme plus fort. Conséquences :
          </p>
          <ul>
            <li>Moins de headroom sur le bus.</li>
            <li>Compresseurs et limiteurs trop agressifs.</li>
            <li>Bas du spectre moins clair au sommatoire.</li>
            <li>Risque accru de distorsion asymétrique.</li>
          </ul>
          <div className="not-prose my-6 rounded-xl border border-teal-500/20 bg-teal-500/10 p-4">
            <p className="text-sm text-teal-100">
              Règle rapide : si la forme d’onde n’est pas centrée sur 0 en zoom,
              il faut corriger le DC offset avant de mixer.
            </p>
          </div>
        </section>

        <section id="como-detectarlo" className="scroll-mt-24">
          <h2>Comment le détecter</h2>
          <ol>
            <li>Utilisez un meter DC ou un analyseur montrant la moyenne.</li>
            <li>Zoomez et vérifiez si l’onde est centrée.</li>
            <li>Calculez la moyenne : si elle n’est pas ~0, il y a offset.</li>
          </ol>
          <pre>
            <code>{`dc_offset = mean(signal)
signal_fixed = signal - dc_offset`}</code>
          </pre>
          <p>
            En pratique, au‑delà de -60 dB, la correction est souvent justifiée.
          </p>
        </section>

        <section id="como-lo-hace-piroola" className="scroll-mt-24">
          <h2>Comment Piroola le traite</h2>
          <p>
            Dans le pipeline, <strong>S1_STEM_DC_OFFSET.py</strong> mesure le DC
            offset et le pic en dBFS. Si la valeur dépasse le seuil
            (<code>dc_offset_max_db</code>), le stage
            <strong> S1_STEM_DC_OFFSET.py</strong> retire la moyenne sur toutes
            les samples sans changer l’équilibre tonal.
          </p>
          <p>
            Cela intervient après normalisation dans
            <strong> S0_SESSION_FORMAT</strong> (conversion interne en WAV).
          </p>
          <ul>
            <li>Analyse chaque stem en mono.</li>
            <li>Corrige uniquement si nécessaire.</li>
            <li>Réécrit des stems propres en temporaire.</li>
          </ul>
        </section>

        <section id="solucion-manual" className="scroll-mt-24">
          <h2>Correction manuelle sûre</h2>
          <ol>
            <li>Insérez un plugin de DC removal ou un EQ avec HPF.</li>
            <li>Commencez à 20 Hz avec une pente douce.</li>
            <li>Vérifiez que l’onde est centrée.</li>
            <li>Exportez sans normalisation ni limiteur.</li>
          </ol>
          <p>Évitez les filtres trop agressifs sur les sub‑bass.</p>
        </section>

        <section id="checklist" className="scroll-mt-24">
          <h2>Checklist avant envoi</h2>
          <ul>
            <li>Fichiers 24‑bit ou 32‑float, pas de dither inutile.</li>
            <li>Pas de clipping visible.</li>
            <li>Silences propres au début et à la fin.</li>
            <li>Pas de normalisation par stem.</li>
            <li>DC offset corrigé ou dans une zone sûre.</li>
          </ul>
        </section>

        <section id="faq" className="scroll-mt-24">
          <h2>FAQ</h2>
          <h3>Le DC offset s’entend‑il ?</h3>
          <p>
            Généralement non, mais il affecte le headroom et la dynamique.
          </p>
          <h3>Un HPF remplace‑t‑il le DC removal ?</h3>
          <p>
            Il aide, mais le DC removal est plus précis et ne touche pas la bande
            audible.
          </p>
          <h3>Puis‑je l’ignorer s’il est faible ?</h3>
          <p>En dessous de -60 dB, c’est souvent acceptable.</p>
        </section>
      </>
    ),
    "compresion-bus-bateria-punch-glue": (
      <>
        <p>
          La compression de bus batterie fait la différence entre un kit cohérent
          et un tas de pistes isolées. Trop forte, elle écrase les transitoires.
          Voici une méthode technique et reproductible.
        </p>

        <section id="por-que-bus" className="scroll-mt-24">
          <h2>Pourquoi compresser le bus batterie</h2>
          <p>
            Le bus agit comme une colle. Une légère compression unifie le kit,
            contrôle les pics et stabilise l’énergie sans tuer l’impact.
          </p>
          <ul>
            <li>Cohésion kick/snare/overheads.</li>
            <li>Pics contrôlés sans aplatir le groove.</li>
            <li>Meilleure intégration dans le mix.</li>
          </ul>
        </section>

        <section id="crest-factor" className="scroll-mt-24">
          <h2>Crest factor et dynamique utile</h2>
          <p>
            Le crest factor est la différence entre le pic et le RMS. Trop haut,
            c’est instable ; trop bas, c’est plat. Un bon range est 6‑10 dB.
          </p>
          <div className="not-prose my-6 rounded-xl border border-violet-500/20 bg-violet-500/10 p-4">
            <p className="text-sm text-violet-100">
              Au‑dessus du range cible, une compression douce du bus redonne de
              la cohésion.
            </p>
          </div>
        </section>

        <section id="ajustes-base" className="scroll-mt-24">
          <h2>Réglages de base</h2>
          <ul>
            <li>Ratio : 2:1 à 4:1 (3:1 est un bon point de départ).</li>
            <li>Attack : 10‑30 ms pour préserver les transitoires.</li>
            <li>Release : 100‑200 ms pour suivre le groove.</li>
            <li>Réduction : 1‑3 dB en moyenne.</li>
          </ul>
        </section>

        <section id="como-lo-hace-piroola" className="scroll-mt-24">
          <h2>Comment Piroola procède</h2>
          <p>
            <strong>S5_BUS_DYNAMICS_DRUMS.py</strong> calcule le crest factor du
            bus. Si la valeur dépasse la cible, une compression de glue est
            appliquée avec une enveloppe commune.
          </p>
          <ul>
            <li>Bus multicanal avec tous les stems de batterie.</li>
            <li>Enveloppe identique sur chaque canal.</li>
            <li>Réécriture des stems avec compression appliquée.</li>
          </ul>
        </section>

        <section id="paso-a-paso" className="scroll-mt-24">
          <h2>Étapes manuelles</h2>
          <ol>
            <li>Routez kick, snare, toms et OH vers un bus dédié.</li>
            <li>Compresseur 3:1, attack 10 ms.</li>
            <li>Réduisez 1‑3 dB sur les pics.</li>
            <li>Ajustez le release au tempo.</li>
          </ol>
        </section>

        <section id="errores-comunes" className="scroll-mt-24">
          <h2>Erreurs fréquentes</h2>
          <ul>
            <li>Attack trop rapide : transitoires écrasés.</li>
            <li>Release trop court : pompage audible.</li>
            <li>Réduction moyenne &gt; 4 dB : batterie sans vie.</li>
          </ul>
        </section>

        <section id="checklist" className="scroll-mt-24">
          <h2>Checklist rapide</h2>
          <ul>
            <li>GR moyenne entre 1‑3 dB.</li>
            <li>Crest factor dans la cible.</li>
            <li>Transitoires kick/snare bien présents.</li>
          </ul>
        </section>
      </>
    ),
    "alineacion-fase-bateria-multimic": (
      <>
        <p>
          En multi‑mic, un léger décalage suffit à créer des annulations. Résultat
          : kick mou, snare creuse, stéréo floue. Voici un workflow fiable.
        </p>

        <section id="sintomas-fase" className="scroll-mt-24">
          <h2>Signes de problèmes de phase</h2>
          <ul>
            <li>Le bas disparaît quand on ajoute les overheads.</li>
            <li>La caisse perd du corps avec les room mics.</li>
            <li>Le mono sonne mieux que le stéréo.</li>
            <li>Corrélation négative.</li>
          </ul>
        </section>

        <section id="por-que-se-pierde" className="scroll-mt-24">
          <h2>Pourquoi la phase bouge</h2>
          <ul>
            <li>Distances différentes entre micros.</li>
            <li>Polarité inversée.</li>
            <li>Latence non compensée.</li>
          </ul>
        </section>

        <section id="como-medir" className="scroll-mt-24">
          <h2>Mesurer et aligner</h2>
          <ol>
            <li>Écoutez en mono et détectez les annulations.</li>
            <li>Vérifiez la corrélation.</li>
            <li>Testez l’inversion de polarité.</li>
            <li>Alignez les transitoires à l’échantillon.</li>
          </ol>
        </section>

        <section id="como-lo-hace-piroola" className="scroll-mt-24">
          <h2>Méthode Piroola</h2>
          <p>
            <strong>S2_GROUP_PHASE_DRUMS.py</strong> analyse les stems de batterie,
            calcule la corrélation et corrige la polarité/alignement pour maximiser
            la cohérence du bus.
          </p>
        </section>

        <section id="paso-a-paso" className="scroll-mt-24">
          <h2>Workflow manuel</h2>
          <ol>
            <li>Kick + overheads en mono.</li>
            <li>Inversez la polarité si le bas s’effondre.</li>
            <li>Alignez les transitoires.</li>
            <li>Répétez avec snare et room.</li>
          </ol>
        </section>

        <section id="errores-comunes" className="scroll-mt-24">
          <h2>Erreurs fréquentes</h2>
          <ul>
            <li>Se fier à la forme d’onde plutôt qu’aux oreilles.</li>
            <li>Tout aligner sans tenir compte du groove.</li>
            <li>Oublier la polarité avant de déplacer.</li>
          </ul>
        </section>

        <section id="checklist" className="scroll-mt-24">
          <h2>Checklist</h2>
          <ul>
            <li>Corrélation stable et positive.</li>
            <li>Bas solide en mono.</li>
            <li>Transitoires nets sans effet de flanger.</li>
          </ul>
        </section>
      </>
    ),
    "control-resonancias-stems": (
      <>
        <p>
          Les résonances sont des pics étroits qui rendent une piste agressive.
          Il faut des coupes chirurgicales, pas des EQ larges.
        </p>

        <section id="que-son-resonancias" className="scroll-mt-24">
          <h2>Que sont les résonances</h2>
          <p>
            Accumulations d’énergie à des fréquences précises, liées à la salle,
            l’instrument ou le micro.
          </p>
        </section>

        <section id="por-que-problema" className="scroll-mt-24">
          <h2>Pourquoi c’est un problème</h2>
          <ul>
            <li>Fatigue auditive.</li>
            <li>Masquage des éléments clés.</li>
            <li>Nécessité de baisser le niveau général.</li>
          </ul>
        </section>

        <section id="como-detectar" className="scroll-mt-24">
          <h2>Comment les détecter</h2>
          <ol>
            <li>Analyseur + pics étroits.</li>
            <li>Balayage EQ avec Q élevé.</li>
            <li>Vérifier la persistance du pic.</li>
          </ol>
        </section>

        <section id="como-lo-hace-piroola" className="scroll-mt-24">
          <h2>Méthode Piroola</h2>
          <p>
            <strong>S4_STEM_RESONANCE_CONTROL.py</strong> repère les résonances
            persistantes et réduit légèrement chaque bande. Puis
            <strong> S4_STEM_HPF_LPF.py</strong> nettoie les extrêmes.
          </p>
        </section>

        <section id="workflow-manual" className="scroll-mt-24">
          <h2>Workflow manuel</h2>
          <ol>
            <li>EQ paramétrique avant compression.</li>
            <li>Balayage +6 dB avec Q élevé.</li>
            <li>Réduction 2‑4 dB par pic.</li>
            <li>EQ dynamique si intermittent.</li>
          </ol>
        </section>

        <section id="errores-comunes" className="scroll-mt-24">
          <h2>Erreurs fréquentes</h2>
          <ul>
            <li>Coupes trop larges.</li>
            <li>Supprimer le caractère.</li>
            <li>Corriger après compression.</li>
          </ul>
        </section>

        <section id="checklist" className="scroll-mt-24">
          <h2>Checklist</h2>
          <ul>
            <li>Moins d’agressivité sans perdre de présence.</li>
            <li>Coupes étroites et contrôlées.</li>
            <li>Dynamique intacte.</li>
          </ul>
        </section>
      </>
    ),
    "lufs-true-peak-loudness": (
      <>
        <p>
          Atteindre le loudness est simple en limitant trop, mais le mix devient
          plat. Il faut comprendre LUFS et true peak pour pousser le niveau sans
          casser la dynamique.
        </p>

        <section id="que-son-lufs" className="scroll-mt-24">
          <h2>Que signifie LUFS</h2>
          <p>
            LUFS mesure la sonorité perçue. L’intégrated couvre tout le morceau,
            le short‑term montre les variations locales.
          </p>
        </section>

        <section id="targets-streaming" className="scroll-mt-24">
          <h2>Targets streaming</h2>
          <p>
            Beaucoup de plateformes normalisent vers -14 LUFS et recommandent
            -1 dBTP. Le genre reste déterminant.
          </p>
          <ul>
            <li>-14 LUFS est une référence, pas une obligation.</li>
            <li>-1 dBTP évite la distorsion codec.</li>
            <li>Comparer avec des titres du même style.</li>
          </ul>
        </section>

        <section id="true-peak" className="scroll-mt-24">
          <h2>True peak et intersample</h2>
          <p>
            Les intersample peaks dépassent 0 dBFS lors de la reconstruction
            analogique. D’où l’importance du true peak.
          </p>
        </section>

        <section id="como-lo-hace-piroola" className="scroll-mt-24">
          <h2>Comment Piroola gère</h2>
          <p>
            <strong>S9_MASTER_GENERIC.py</strong> prépare la limitation finale et
            <strong> S10_MASTER_FINAL_LIMITS.py</strong> vérifie LUFS, true peak
            et corrélation pour ajuster finement.
          </p>
        </section>

        <section id="paso-a-paso" className="scroll-mt-24">
          <h2>Étapes manuelles</h2>
          <ol>
            <li>Mesurez LUFS et true peak.</li>
            <li>Ceiling entre -1 et -0,5 dBTP.</li>
            <li>Ajustez le threshold vers le LUFS cible.</li>
            <li>Écoutez pompage ou distorsion.</li>
          </ol>
        </section>

        <section id="errores-comunes" className="scroll-mt-24">
          <h2>Erreurs fréquentes</h2>
          <ul>
            <li>Limiter trop fort et tuer les transitoires.</li>
            <li>Ignorer le true peak.</li>
            <li>Forcer un target inadapté au genre.</li>
          </ul>
        </section>

        <section id="checklist" className="scroll-mt-24">
          <h2>Checklist</h2>
          <ul>
            <li>LUFS intégrés dans la cible.</li>
            <li>True peak sous le plafond de sécurité.</li>
            <li>Dynamique préservée.</li>
          </ul>
        </section>
      </>
    ),
  },
  de: {
    "como-eliminar-dc-offset-en-stems": (
      <>
        <p>
          DC Offset ist ein stilles Problem: Man hört es nicht, aber Meter,
          Kompressoren und Headroom leiden. Wenn Stems verschoben ankommen,
          startet der Mixbus mit weniger Reserve und Dynamikprozessoren reagieren
          ungleichmäßig.
        </p>

        <section id="que-es-el-dc-offset" className="scroll-mt-24">
          <h2>Was ist DC Offset</h2>
          <p>
            Im Digitalaudio sollte die Wellenform um 0 schwingen. DC Offset
            bedeutet eine konstante Verschiebung nach oben oder unten. Ursachen
            sind Wandler, falsch kalibrierte Plugins oder fehlerhafte Exporte.
          </p>
          <ul>
            <li>Extrem tieffrequente Energie (nahe 0 Hz).</li>
            <li>Keine musikalische Information.</li>
            <li>Weniger Headroom und verzerrte Dynamik.</li>
          </ul>
        </section>

        <section id="por-que-importa" className="scroll-mt-24">
          <h2>Warum es wichtig ist</h2>
          <ul>
            <li>Weniger Headroom im Mixbus.</li>
            <li>Kompressoren reagieren zu aggressiv.</li>
            <li>Matschiger Low‑End‑Sum.</li>
            <li>Mehr Risiko für asymmetrische Verzerrung.</li>
          </ul>
          <div className="not-prose my-6 rounded-xl border border-teal-500/20 bg-teal-500/10 p-4">
            <p className="text-sm text-teal-100">
              Kurzregel: Ist die Wellenform nicht um 0 zentriert, sollte man DC
              Offset vor dem Mix entfernen.
            </p>
          </div>
        </section>

        <section id="como-detectarlo" className="scroll-mt-24">
          <h2>So erkennst du es schnell</h2>
          <ol>
            <li>DC‑Meter oder Analyzer mit Mittelwert nutzen.</li>
            <li>Hereinzoomen und die Mitte prüfen.</li>
            <li>Mittelwert berechnen: Nicht ~0 = Offset.</li>
          </ol>
          <pre>
            <code>{`dc_offset = mean(signal)
signal_fixed = signal - dc_offset`}</code>
          </pre>
        </section>

        <section id="como-lo-hace-piroola" className="scroll-mt-24">
          <h2>So macht es Piroola</h2>
          <p>
            <strong>S1_STEM_DC_OFFSET.py</strong> misst DC Offset und Peak dBFS
            pro Stem. Überschreitet es den Grenzwert (
            <code>dc_offset_max_db</code>), zieht das Stage den Mittelwert von
            allen Samples ab.
          </p>
          <p>
            Nach der Formatnormalisierung in
            <strong> S0_SESSION_FORMAT</strong> ist die Analyse konsistent.
          </p>
          <ul>
            <li>Mono‑Analyse pro Stem.</li>
            <li>Korrektur nur bei Bedarf.</li>
            <li>Re‑Write der bereinigten Stems.</li>
          </ul>
        </section>

        <section id="solucion-manual" className="scroll-mt-24">
          <h2>Sichere manuelle Lösung</h2>
          <ol>
            <li>DC‑Removal‑Plugin oder EQ mit HPF einsetzen.</li>
            <li>Bei HPF bei 20 Hz starten, sanfte Flanke.</li>
            <li>Wellenform erneut zentriert prüfen.</li>
            <li>Ohne Normalisierung/Limit exportieren.</li>
          </ol>
        </section>

        <section id="checklist" className="scroll-mt-24">
          <h2>Checklist vor dem Upload</h2>
          <ul>
            <li>24‑bit oder 32‑float, kein unnötiges Dither.</li>
            <li>Kein sichtbares Clipping.</li>
            <li>Saubere Stille am Anfang/Ende.</li>
            <li>Keine Stem‑Normalisierung.</li>
            <li>DC Offset korrigiert oder sicher.</li>
          </ul>
        </section>

        <section id="faq" className="scroll-mt-24">
          <h2>FAQ</h2>
          <h3>Hört man DC Offset?</h3>
          <p>Meist nicht, aber er beeinflusst Headroom und Dynamik.</p>
          <h3>Ersetzt HPF das DC Removal?</h3>
          <p>Nur teilweise. DC Removal ist präziser.</p>
          <h3>Kann ich es ignorieren, wenn es klein ist?</h3>
          <p>
            Wenn es deutlich unter -60 dB liegt, ist es meist ok. Bei Sub-Stems
            zählt jeder dB Headroom.
          </p>
        </section>
      </>
    ),
    "compresion-bus-bateria-punch-glue": (
      <>
        <p>
          Drum‑Bus‑Kompression verbindet den Kit‑Sound. Zu viel davon zerstört
          Transienten und Punch. Hier ist eine reproduzierbare Methode.
        </p>

        <section id="por-que-bus" className="scroll-mt-24">
          <h2>Warum Drum‑Bus‑Kompression</h2>
          <ul>
            <li>Mehr Kohäsion zwischen Kick, Snare und Overheads.</li>
            <li>Pegelige Peaks ohne Groove‑Verlust.</li>
            <li>Besseres Sitzen im Mix.</li>
          </ul>
        </section>

        <section id="crest-factor" className="scroll-mt-24">
          <h2>Crest Factor und Dynamik</h2>
          <p>
            6‑10 dB Crest sind ein guter Zielbereich. Darüber hilft sanfte
            Bus‑Kompression.
          </p>
        </section>

        <section id="ajustes-base" className="scroll-mt-24">
          <h2>Basis‑Settings</h2>
          <ul>
            <li>Ratio 2:1‑4:1 (3:1 als Start).</li>
            <li>Attack 10‑30 ms, Release 100‑200 ms.</li>
            <li>1‑3 dB durchschnittliche Reduktion.</li>
          </ul>
        </section>

        <section id="como-lo-hace-piroola" className="scroll-mt-24">
          <h2>Piroola‑Ansatz</h2>
          <p>
            <strong>S5_BUS_DYNAMICS_DRUMS.py</strong> berechnet den Crest Factor
            und komprimiert bei Bedarf mit gemeinsamer Hüllkurve.
          </p>
        </section>

        <section id="paso-a-paso" className="scroll-mt-24">
          <h2>Manueller Ablauf</h2>
          <ol>
            <li>Drums auf einen Bus routen.</li>
            <li>Kompressor 3:1, Attack 10 ms.</li>
            <li>1‑3 dB Peaks reduzieren.</li>
            <li>Release ans Tempo anpassen.</li>
          </ol>
        </section>

        <section id="errores-comunes" className="scroll-mt-24">
          <h2>Häufige Fehler</h2>
          <ul>
            <li>Attack zu schnell.</li>
            <li>Release zu kurz.</li>
            <li>Zu viel GR (&gt; 4 dB).</li>
          </ul>
        </section>

        <section id="checklist" className="scroll-mt-24">
          <h2>Checklist</h2>
          <ul>
            <li>Durchschnittliche GR 1-3 dB.</li>
            <li>Crest Factor im Zielbereich.</li>
            <li>Kick/Snare-Transienten bleiben präsent.</li>
            <li>Kein Pumpen in Hi-Hats oder Overheads.</li>
          </ul>
        </section>
      </>
    ),
    "alineacion-fase-bateria-multimic": (
      <>
        <p>
          Mehrere Mikrofone bedeuten mehr Phasenrisiko. Ein kleiner Versatz kann
          Low‑End löschen. So alignierst du sicher.
        </p>

        <section id="sintomas-fase" className="scroll-mt-24">
          <h2>Symptome</h2>
          <ul>
            <li>Low‑End verschwindet mit Overheads.</li>
            <li>Snare klingt hohl mit Room‑Mics.</li>
            <li>Mono klingt besser.</li>
          </ul>
        </section>

        <section id="por-que-se-pierde" className="scroll-mt-24">
          <h2>Warum Phase verloren geht</h2>
          <ul>
            <li>Unterschiedliche Abstände.</li>
            <li>Polaritärswechsel.</li>
            <li>Unkompensierte Latenz.</li>
          </ul>
        </section>

        <section id="como-medir" className="scroll-mt-24">
          <h2>Messen und ausrichten</h2>
          <ol>
            <li>Mono‑Check und Korrelation prüfen.</li>
            <li>Polarity flip testen.</li>
            <li>Transienten auf Sample‑Ebene alignen.</li>
          </ol>
        </section>

        <section id="como-lo-hace-piroola" className="scroll-mt-24">
          <h2>Piroola-Methode</h2>
          <p>
            <strong>S2_GROUP_PHASE_DRUMS.py</strong> analysiert Korrelation und
            richtet Zeit/Polarität für den Drum-Bus aus.
          </p>
        </section>

        <section id="paso-a-paso" className="scroll-mt-24">
          <h2>Schritt für Schritt</h2>
          <ol>
            <li>Kick + Overheads in Mono prüfen.</li>
            <li>Polarity-Flip testen, wenn das Low-End verschwindet.</li>
            <li>Haupttransienten auf Sample-Ebene ausrichten.</li>
            <li>Mit Snare und Room-Mics wiederholen.</li>
          </ol>
        </section>

        <section id="errores-comunes" className="scroll-mt-24">
          <h2>Häufige Fehler</h2>
          <ul>
            <li>Nur auf die Wellenform schauen, nicht aufs Gehör.</li>
            <li>Alles auf den gleichen Punkt schieben und den Groove verlieren.</li>
            <li>Polarity-Check vergessen, bevor man verschiebt.</li>
          </ul>
        </section>

        <section id="checklist" className="scroll-mt-24">
          <h2>Checklist</h2>
          <ul>
            <li>Stabile, positive Korrelation.</li>
            <li>Low-End bleibt in Mono solide.</li>
            <li>Transienten definiert, kein Flanger-Eindruck.</li>
          </ul>
        </section>
      </>
    ),
    "control-resonancias-stems": (
      <>
        <p>
          Resonanzen sind schmale Peaks, die Tracks scharf klingen lassen.
          Chirurgische Cuts sind nötig, keine breite EQ‑Absenkung.
        </p>

        <section id="que-son-resonancias" className="scroll-mt-24">
          <h2>Was Resonanzen sind</h2>
          <p>Persistente Energie in schmalen Frequenzbereichen.</p>
        </section>

        <section id="por-que-problema" className="scroll-mt-24">
          <h2>Warum problematisch</h2>
          <ul>
            <li>Hörermüdung.</li>
            <li>Maskierung wichtiger Elemente.</li>
            <li>Geringerer Gesamt‑Level.</li>
          </ul>
        </section>

        <section id="como-detectar" className="scroll-mt-24">
          <h2>Erkennen</h2>
          <ol>
            <li>Analyzer nutzen und schmale Peaks suchen.</li>
            <li>EQ‑Sweep mit hohem Q.</li>
            <li>Persistenz prüfen.</li>
          </ol>
        </section>

        <section id="como-lo-hace-piroola" className="scroll-mt-24">
          <h2>Piroola-Methode</h2>
          <p>
            <strong>S4_STEM_RESONANCE_CONTROL.py</strong> reduziert Resonanzen,
            danach säubert <strong>S4_STEM_HPF_LPF.py</strong> die Ränder.
          </p>
        </section>

        <section id="workflow-manual" className="scroll-mt-24">
          <h2>Manueller Workflow</h2>
          <ol>
            <li>Parametrischen EQ vor der Kompression einsetzen.</li>
            <li>Mit +6 dB und hohem Q sweepen, um Resonanzen zu finden.</li>
            <li>Jeden Peak um 2-4 dB absenken.</li>
            <li>Bei sporadischen Peaks dynamischen EQ nutzen.</li>
          </ol>
        </section>

        <section id="errores-comunes" className="scroll-mt-24">
          <h2>Häufige Fehler</h2>
          <ul>
            <li>Zu breite Cuts, der Sound wird dünn.</li>
            <li>Resonanzen entfernen, die zum Charakter gehören.</li>
            <li>Nach der Kompression korrigieren und das Problem verstärken.</li>
          </ul>
        </section>

        <section id="checklist" className="scroll-mt-24">
          <h2>Checklist</h2>
          <ul>
            <li>Weniger Härte ohne Präsenzverlust.</li>
            <li>Schmale, kontrollierte Cuts.</li>
            <li>Dynamik bleibt vor der Kompression intakt.</li>
          </ul>
        </section>
      </>
    ),
    "lufs-true-peak-loudness": (
      <>
        <p>
          Lautheit erreicht man schnell mit hartem Limiting, aber der Mix wird
          flach. LUFS und True Peak helfen, sauber laut zu werden.
        </p>

        <section id="que-son-lufs" className="scroll-mt-24">
          <h2>Was LUFS bedeutet</h2>
          <p>LUFS misst wahrgenommene Lautheit über die Zeit.</p>
        </section>

        <section id="targets-streaming" className="scroll-mt-24">
          <h2>Streaming‑Ziele</h2>
          <ul>
            <li>≈ -14 LUFS als Referenz.</li>
            <li>-1 dBTP für Codec‑Sicherheit.</li>
          </ul>
        </section>

        <section id="true-peak" className="scroll-mt-24">
          <h2>True Peak</h2>
          <p>
            Intersample‑Peaks entstehen bei der Rekonstruktion. True Peak schützt
            davor.
          </p>
        </section>

        <section id="como-lo-hace-piroola" className="scroll-mt-24">
          <h2>Piroola-Workflow</h2>
          <p>
            <strong>S9_MASTER_GENERIC.py</strong> und
            <strong> S10_MASTER_FINAL_LIMITS.py</strong> steuern LUFS und True
            Peak mit Mikro-Korrekturen.
          </p>
        </section>

        <section id="paso-a-paso" className="scroll-mt-24">
          <h2>Manueller Ablauf</h2>
          <ol>
            <li>LUFS und True Peak messen.</li>
            <li>Ceiling zwischen -1 und -0,5 dBTP setzen.</li>
            <li>Threshold absenken, bis Ziel-LUFS erreicht.</li>
            <li>Auf Pumpen oder Verzerrung achten.</li>
          </ol>
        </section>

        <section id="errores-comunes" className="scroll-mt-24">
          <h2>Häufige Fehler</h2>
          <ul>
            <li>Zu hart limiten und Transienten zerstören.</li>
            <li>True Peak ignorieren.</li>
            <li>Targets erzwingen, die nicht zum Genre passen.</li>
          </ul>
        </section>

        <section id="checklist" className="scroll-mt-24">
          <h2>Checklist</h2>
          <ul>
            <li>Integrierte LUFS im Zielbereich.</li>
            <li>True Peak unter sicherem Ceiling.</li>
            <li>Dynamik bleibt erhalten.</li>
          </ul>
        </section>
      </>
    ),
  },
  it: {
    "como-eliminar-dc-offset-en-stems": (
      <>
        <p>
          Il DC offset è un problema silenzioso: non lo senti, ma lo soffrono i
          meter, i compressori e l’headroom complessivo. Se gli stem arrivano con
          uno spostamento costante rispetto allo zero, il bus parte con meno
          margine e la dinamica reagisce in modo instabile.
        </p>

        <section id="que-es-el-dc-offset" className="scroll-mt-24">
          <h2>Cos’è il DC offset</h2>
          <p>
            In digitale l’onda dovrebbe oscillare intorno allo zero. Il DC offset
            appare quando la forma d’onda è spostata verso l’alto o il basso, come
            se avesse una media fissa. Le cause includono converter, plugin
            mal calibrati o export difettosi.
          </p>
          <ul>
            <li>Energia a frequenza quasi zero.</li>
            <li>Nessuna informazione musicale utile.</li>
            <li>Meno headroom e dinamica alterata.</li>
          </ul>
        </section>

        <section id="por-que-importa" className="scroll-mt-24">
          <h2>Perché è importante</h2>
          <ul>
            <li>Headroom ridotto sul mix bus.</li>
            <li>Compressori più aggressivi.</li>
            <li>Bassi meno definiti nella somma.</li>
            <li>Rischio di distorsione asimmetrica.</li>
          </ul>
        </section>

        <section id="como-detectarlo" className="scroll-mt-24">
          <h2>Come rilevarlo</h2>
          <ol>
            <li>Usa un meter DC o un analizzatore con valore medio.</li>
            <li>Zooma e controlla se la forma d’onda è centrata.</li>
            <li>Se la media non è ~0, c’è offset.</li>
          </ol>
        </section>

        <section id="como-lo-hace-piroola" className="scroll-mt-24">
          <h2>Come lo fa Piroola</h2>
          <p>
            <strong>S1_STEM_DC_OFFSET.py</strong> misura DC offset e peak dBFS. Se
            supera il limite (<code>dc_offset_max_db</code>), lo stage sottrae la
            media da tutti i campioni.
          </p>
          <p>
            Dopo <strong>S0_SESSION_FORMAT</strong> l’analisi è consistente tra
            sample rate.
          </p>
        </section>

        <section id="solucion-manual" className="scroll-mt-24">
          <h2>Correzione manuale sicura</h2>
          <ol>
            <li>Plugin DC removal o EQ con HPF.</li>
            <li>Parti da 20 Hz con pendenza morbida.</li>
            <li>Controlla che l’onda sia centrata.</li>
            <li>Esporta senza normalizzare o limitare.</li>
          </ol>
        </section>

        <section id="checklist" className="scroll-mt-24">
          <h2>Checklist</h2>
          <ul>
            <li>File 24‑bit o 32‑float.</li>
            <li>Nessun clipping visibile.</li>
            <li>Silenzio pulito in testa e coda.</li>
            <li>Non normalizzare ogni stem.</li>
            <li>DC offset corretto o sicuro.</li>
          </ul>
        </section>

        <section id="faq" className="scroll-mt-24">
          <h2>FAQ</h2>
          <h3>Il DC offset si sente?</h3>
          <p>Di solito no, ma riduce headroom e altera la dinamica.</p>
          <h3>Un high-pass sostituisce il DC removal?</h3>
          <p>
            Può aiutare, ma il DC removal è più preciso e non tocca la banda
            udibile.
          </p>
          <h3>Posso ignorarlo se è molto piccolo?</h3>
          <p>
            Se è ben sotto i -60 dB è spesso ok, ma con stem ricchi di sub ogni
            dB conta.
          </p>
        </section>
      </>
    ),
    "compresion-bus-bateria-punch-glue": (
      <>
        <p>
          La compressione del bus batteria unisce il kit. Se esageri, perdi
          transitori e punch. Ecco un metodo tecnico e ripetibile.
        </p>

        <section id="por-que-bus" className="scroll-mt-24">
          <h2>Perché comprimere il bus batteria</h2>
          <ul>
            <li>Coesione tra kick, snare e overhead.</li>
            <li>Picchi controllati senza schiacciare il groove.</li>
            <li>Più solidità nel mix.</li>
          </ul>
        </section>

        <section id="crest-factor" className="scroll-mt-24">
          <h2>Crest factor e dinamica utile</h2>
          <p>Un range tipico è 6‑10 dB, a seconda dello stile.</p>
        </section>

        <section id="ajustes-base" className="scroll-mt-24">
          <h2>Settaggi base</h2>
          <ul>
            <li>Ratio 2:1‑4:1 (3:1 come base).</li>
            <li>Attack 10‑30 ms, Release 100‑200 ms.</li>
            <li>Riduzione media 1‑3 dB.</li>
          </ul>
        </section>

        <section id="como-lo-hace-piroola" className="scroll-mt-24">
          <h2>Come lo fa Piroola</h2>
          <p>
            <strong>S5_BUS_DYNAMICS_DRUMS.py</strong> calcola il crest factor e
            applica una compressione glue con envelope comune se necessario.
          </p>
        </section>

        <section id="paso-a-paso" className="scroll-mt-24">
          <h2>Passo per passo</h2>
          <ol>
            <li>Routa kick, snare, tom e overhead su un bus.</li>
            <li>Inserisci un compressore ratio 3:1 con attack 10 ms.</li>
            <li>Riduci 1‑3 dB sui picchi più forti.</li>
            <li>Regola il release seguendo il groove.</li>
            <li>Se manca punch, aumenta l’attack o riduci il ratio.</li>
          </ol>
          <p>
            Se vuoi più densità senza perdere impatto, usa la compressione
            parallela.
          </p>
        </section>

        <section id="errores-comunes" className="scroll-mt-24">
          <h2>Errori comuni</h2>
          <ul>
            <li>Attack troppo veloce: transienti schiacciati.</li>
            <li>Release troppo corto: pumping udibile.</li>
            <li>Più di 4 dB di GR media: batteria senza vita.</li>
            <li>Non ascoltare il low‑end: il kick perde definizione.</li>
          </ul>
        </section>

        <section id="checklist" className="scroll-mt-24">
          <h2>Checklist</h2>
          <ul>
            <li>GR media 1‑3 dB.</li>
            <li>Crest factor nel range target.</li>
            <li>Transienti di kick e snare ancora presenti.</li>
            <li>Niente pumping su hi‑hat o overhead.</li>
          </ul>
        </section>
      </>
    ),
    "alineacion-fase-bateria-multimic": (
      <>
        <p>
          Nei setup multi‑mic piccoli ritardi causano cancellazioni. Il risultato
          è un kick debole o una snare vuota. Ecco come allineare la fase.
        </p>

        <section id="sintomas-fase" className="scroll-mt-24">
          <h2>Sintomi</h2>
          <ul>
            <li>Low‑end che sparisce con gli overhead.</li>
            <li>Snare che perde corpo con i room mics.</li>
            <li>Mono più solido dello stereo.</li>
          </ul>
        </section>

        <section id="por-que-se-pierde" className="scroll-mt-24">
          <h2>Perché si perde la fase</h2>
          <p>
            Ogni microfono è a distanza diversa dal fusto, quindi la fase si
            sposta. Polarità invertita o latenza non compensata peggiorano la
            somma.
          </p>
          <ul>
            <li>Differenze di distanza tra microfoni.</li>
            <li>Polarità invertita su preamp o plugin.</li>
            <li>Latenza non compensata su processori esterni.</li>
          </ul>
        </section>

        <section id="como-medir" className="scroll-mt-24">
          <h2>Misurare e allineare</h2>
          <ol>
            <li>Ascolta in mono e individua le cancellazioni.</li>
            <li>Verifica la correlazione.</li>
            <li>Inverti la polarità se serve.</li>
            <li>Allinea i transienti al campione.</li>
          </ol>
        </section>

        <section id="como-lo-hace-piroola" className="scroll-mt-24">
          <h2>Come lo fa Piroola</h2>
          <p>
            <strong>S2_GROUP_PHASE_DRUMS.py</strong> identifica gli stem di
            batteria e misura la correlazione. Lo stage applica allineamento
            temporale e correzione di polarità per massimizzare la coerenza del
            bus senza cambiare il bilanciamento.
          </p>
          <ul>
            <li>Individua coppie problematiche tra kick, snare e overhead.</li>
            <li>Corregge gli offset temporali a livello di campione.</li>
            <li>Valida la coerenza con metriche di fase.</li>
          </ul>
        </section>

        <section id="paso-a-paso" className="scroll-mt-24">
          <h2>Passo per passo</h2>
          <ol>
            <li>Seleziona kick + overhead e controlla la somma in mono.</li>
            <li>Inverti la polarità dove il low‑end scompare.</li>
            <li>Allinea i transienti principali nel sample editor.</li>
            <li>Ripeti con snare e room mics.</li>
          </ol>
        </section>

        <section id="errores-comunes" className="scroll-mt-24">
          <h2>Errori comuni</h2>
          <ul>
            <li>Fidarsi solo della forma d’onda e non dell’orecchio.</li>
            <li>Allineare tutto allo stesso punto senza considerare il groove.</li>
            <li>Dimenticare la polarità prima di spostare i sample.</li>
          </ul>
        </section>

        <section id="checklist" className="scroll-mt-24">
          <h2>Checklist</h2>
          <ul>
            <li>Correlazione stabile e positiva.</li>
            <li>Low‑end solido in mono.</li>
            <li>Transienti definiti senza effetto flanger.</li>
          </ul>
        </section>
      </>
    ),
    "control-resonancias-stems": (
      <>
        <p>
          Le risonanze sono picchi stretti che rendono una traccia aspra. Serve
          EQ chirurgica per non perdere il timbro.
        </p>

        <section id="que-son-resonancias" className="scroll-mt-24">
          <h2>Cosa sono le risonanze</h2>
          <p>
            Sono accumuli di energia in bande molto strette, dovuti alla stanza,
            allo strumento o al microfono. Quando si sommano più stem, queste
            frequenze diventano fastidiose.
          </p>
        </section>

        <section id="por-que-problema" className="scroll-mt-24">
          <h2>Perché sono un problema</h2>
          <ul>
            <li>Affaticano l’orecchio negli ascolti lunghi.</li>
            <li>Mascherano voce ed elementi principali.</li>
            <li>Costringono ad abbassare il livello globale.</li>
          </ul>
        </section>

        <section id="como-detectar" className="scroll-mt-24">
          <h2>Come individuarle</h2>
          <ol>
            <li>Analizzatore + picchi stretti.</li>
            <li>Sweep con Q alto.</li>
            <li>Tagli 2‑4 dB sui picchi.</li>
          </ol>
        </section>

        <section id="como-lo-hace-piroola" className="scroll-mt-24">
          <h2>Come lo fa Piroola</h2>
          <p>
            <strong>S4_STEM_RESONANCE_CONTROL.py</strong> rileva risonanze
            persistenti e applica riduzioni leggere per banda. Poi
            <strong> S4_STEM_HPF_LPF.py</strong> ripulisce le estremità.
          </p>
          <ul>
            <li>Identifica picchi stretti per stem.</li>
            <li>Applica tagli di pochi dB con Q alto.</li>
            <li>Evita di alterare il timbro principale.</li>
          </ul>
        </section>

        <section id="workflow-manual" className="scroll-mt-24">
          <h2>Workflow manuale</h2>
          <ol>
            <li>Inserisci un EQ parametrico prima della compressione.</li>
            <li>Fai sweep con +6 dB e Q alto per trovare le risonanze.</li>
            <li>Taglia 2‑4 dB su ogni picco individuato.</li>
            <li>Se il picco compare solo a tratti, usa EQ dinamica.</li>
          </ol>
        </section>

        <section id="errores-comunes" className="scroll-mt-24">
          <h2>Errori comuni</h2>
          <ul>
            <li>Tagli troppo larghi che assottigliano il suono.</li>
            <li>Rimuovere risonanze che fanno parte del carattere.</li>
            <li>Correggere dopo la compressione e peggiorare il problema.</li>
          </ul>
        </section>

        <section id="checklist" className="scroll-mt-24">
          <h2>Checklist</h2>
          <ul>
            <li>Meno asprezza senza perdere presenza.</li>
            <li>Tagli stretti e controllati.</li>
            <li>Dinamica intatta prima della compressione.</li>
          </ul>
        </section>
      </>
    ),
    "lufs-true-peak-loudness": (
      <>
        <p>
          Arrivare al loudness è facile limitando troppo, ma il mix diventa piatto.
          LUFS e true peak servono per alzare il volume senza distruggere la
          dinamica.
        </p>

        <section id="que-son-lufs" className="scroll-mt-24">
          <h2>Cosa significa LUFS</h2>
          <p>LUFS misura la loudness percepita nel tempo.</p>
        </section>

        <section id="targets-streaming" className="scroll-mt-24">
          <h2>Target streaming</h2>
          <p>
            Molte piattaforme normalizzano intorno a -14 LUFS integrati e
            consigliano -1 dBTP di true peak. Non è una regola fissa: il genere
            conta.
          </p>
          <ul>
            <li>-14 LUFS è un riferimento, non un obbligo.</li>
            <li>-1 dBTP aiuta a evitare distorsione in codifica.</li>
            <li>Valuta sempre nel contesto del genere.</li>
          </ul>
        </section>

        <section id="true-peak" className="scroll-mt-24">
          <h2>True peak e intersample peaks</h2>
          <p>
            I picchi intersample compaiono quando la ricostruzione analogica
            supera 0 dBFS anche se il file non clippera. Per questo il true peak
            è fondamentale in mastering.
          </p>
        </section>

        <section id="como-lo-hace-piroola" className="scroll-mt-24">
          <h2>Come lo fa Piroola</h2>
          <p>
            <strong>S9_MASTER_GENERIC.py</strong> prepara il limiter finale e
            <strong> S10_MASTER_FINAL_LIMITS.py</strong> verifica LUFS e true
            peak.
          </p>
        </section>

        <section id="paso-a-paso" className="scroll-mt-24">
          <h2>Passo per passo</h2>
          <ol>
            <li>Misura LUFS e true peak.</li>
            <li>Imposta il ceiling tra -1 e -0,5 dBTP.</li>
            <li>Abbassa il threshold fino al LUFS target.</li>
            <li>Ascolta pumping o distorsione.</li>
          </ol>
        </section>

        <section id="errores-comunes" className="scroll-mt-24">
          <h2>Errori comuni</h2>
          <ul>
            <li>Limitare troppo e perdere i transienti.</li>
            <li>Ignorare il true peak.</li>
            <li>Forzare target non adatti al genere.</li>
          </ul>
        </section>

        <section id="checklist" className="scroll-mt-24">
          <h2>Checklist</h2>
          <ul>
            <li>LUFS integrati nel target.</li>
            <li>True peak sotto il ceiling sicuro.</li>
            <li>Dinamica preservata.</li>
          </ul>
        </section>
      </>
    ),
  },
  pt: {
    "como-eliminar-dc-offset-en-stems": (
      <>
        <p>
          DC offset é um problema silencioso: não dá para ouvir, mas afeta
          medidores, compressores e o headroom total. Se os stems chegam
          deslocados, o bus começa com menos margem e a dinâmica reage mal.
        </p>

        <section id="que-es-el-dc-offset" className="scroll-mt-24">
          <h2>O que é DC offset</h2>
          <p>
            No áudio digital a onda deveria oscilar em torno de 0. O DC offset
            aparece quando a forma de onda fica deslocada para cima ou para
            baixo, como se tivesse uma média fixa.
          </p>
          <ul>
            <li>Energia de frequência quase zero.</li>
            <li>Sem informação musical útil.</li>
            <li>Menos headroom e dinâmica alterada.</li>
          </ul>
        </section>

        <section id="por-que-importa" className="scroll-mt-24">
          <h2>Por que isso importa</h2>
          <ul>
            <li>Menos headroom no bus.</li>
            <li>Compressão mais agressiva.</li>
            <li>Low‑end menos claro na soma.</li>
            <li>Maior risco de distorção assimétrica.</li>
          </ul>
        </section>

        <section id="como-detectarlo" className="scroll-mt-24">
          <h2>Como detectar rápido</h2>
          <ol>
            <li>Use um medidor DC ou analizador com valor médio.</li>
            <li>Faça zoom e verifique se a onda está centrada.</li>
            <li>Se a média não é ~0, há offset.</li>
          </ol>
        </section>

        <section id="como-lo-hace-piroola" className="scroll-mt-24">
          <h2>Como a Piroola faz</h2>
          <p>
            <strong>S1_STEM_DC_OFFSET.py</strong> mede DC offset e pico em dBFS.
            Se exceder o limite (<code>dc_offset_max_db</code>), o stage subtrai
            a média de todas as amostras.
          </p>
          <ul>
            <li>Análise mono por stem.</li>
            <li>Correção apenas quando necessário.</li>
            <li>Regrava stems limpos.</li>
          </ul>
        </section>

        <section id="solucion-manual" className="scroll-mt-24">
          <h2>Correção manual segura</h2>
          <ol>
            <li>Use um plugin de DC removal ou EQ com HPF.</li>
            <li>Comece em 20 Hz com inclinação suave.</li>
            <li>Confira se a onda voltou ao centro.</li>
            <li>Exporte sem normalizar ou limitar.</li>
          </ol>
        </section>

        <section id="checklist" className="scroll-mt-24">
          <h2>Checklist</h2>
          <ul>
            <li>Arquivos 24‑bit ou 32‑float.</li>
            <li>Sem clipping visível.</li>
            <li>Silêncio limpo no início/fim.</li>
            <li>DC offset corrigido ou seguro.</li>
          </ul>
        </section>

        <section id="faq" className="scroll-mt-24">
          <h2>FAQ</h2>
          <h3>É possível ouvir DC offset?</h3>
          <p>Normalmente não, mas ele reduz headroom e afeta a dinâmica.</p>
          <h3>HPF substitui DC removal?</h3>
          <p>Ajuda, mas não é tão preciso quanto um DC removal.</p>
        </section>
      </>
    ),
    "compresion-bus-bateria-punch-glue": (
      <>
        <p>
          A compressão no bus de bateria cola o kit. Exagerar destrói transientes
          e punch. Aqui vai um método confiável.
        </p>

        <section id="por-que-bus" className="scroll-mt-24">
          <h2>Por que comprimir o bus de bateria</h2>
          <ul>
            <li>Mais coesão entre kick, snare e overheads.</li>
            <li>Picos controlados sem matar o groove.</li>
            <li>Melhor encaixe no mix.</li>
          </ul>
        </section>

        <section id="crest-factor" className="scroll-mt-24">
          <h2>Crest factor e dinâmica útil</h2>
          <p>Um range típico é 6‑10 dB, dependendo do estilo.</p>
        </section>

        <section id="ajustes-base" className="scroll-mt-24">
          <h2>Ajustes base</h2>
          <ul>
            <li>Ratio 2:1‑4:1 (3:1 como base).</li>
            <li>Attack 10‑30 ms, Release 100‑200 ms.</li>
            <li>Redução média 1‑3 dB.</li>
          </ul>
        </section>

        <section id="como-lo-hace-piroola" className="scroll-mt-24">
          <h2>Como a Piroola faz</h2>
          <p>
            <strong>S5_BUS_DYNAMICS_DRUMS.py</strong> calcula o crest factor do
            bus e aplica compressão glue quando necessário.
          </p>
        </section>

        <section id="paso-a-paso" className="scroll-mt-24">
          <h2>Passo a passo</h2>
          <ol>
            <li>Envie os drums para um bus dedicado.</li>
            <li>Compressor 3:1 com attack 10 ms.</li>
            <li>Reduza 1‑3 dB nos picos.</li>
            <li>Ajuste release ao tempo da música.</li>
          </ol>
        </section>

        <section id="errores-comunes" className="scroll-mt-24">
          <h2>Erros comuns</h2>
          <ul>
            <li>Attack rápido demais e transientes achatados.</li>
            <li>Release curto demais com pumping.</li>
            <li>GR média acima de 4 dB.</li>
          </ul>
        </section>

        <section id="checklist" className="scroll-mt-24">
          <h2>Checklist</h2>
          <ul>
            <li>GR média 1‑3 dB.</li>
            <li>Crest factor dentro da meta.</li>
            <li>Transientes preservados.</li>
          </ul>
        </section>
      </>
    ),
    "alineacion-fase-bateria-multimic": (
      <>
        <p>
          Em gravações multi‑mic, pequenos atrasos causam cancelamentos. O kick
          perde peso e a caixa fica oca. Veja como alinhar a fase.
        </p>

        <section id="sintomas-fase" className="scroll-mt-24">
          <h2>Sintomas de fase</h2>
          <ul>
            <li>Low‑end some ao somar overheads.</li>
            <li>Snare perde corpo com room mics.</li>
            <li>Mono soa mais sólido.</li>
          </ul>
        </section>

        <section id="por-que-se-pierde" className="scroll-mt-24">
          <h2>Por que a fase se perde</h2>
          <ul>
            <li>Diferença de distância entre microfones.</li>
            <li>Polaridade invertida.</li>
            <li>Latência não compensada.</li>
          </ul>
        </section>

        <section id="como-medir" className="scroll-mt-24">
          <h2>Como medir e alinhar</h2>
          <ol>
            <li>Ouça em mono e identifique cancelamentos.</li>
            <li>Verifique a correlação.</li>
            <li>Teste inversão de polaridade.</li>
            <li>Alinhe transientes por amostra.</li>
          </ol>
        </section>

        <section id="como-lo-hace-piroola" className="scroll-mt-24">
          <h2>Como a Piroola faz</h2>
          <p>
            <strong>S2_GROUP_PHASE_DRUMS.py</strong> analisa correlação e aplica
            alinhamento temporal/polaridade no bus de drums.
          </p>
        </section>

        <section id="paso-a-paso" className="scroll-mt-24">
          <h2>Workflow manual</h2>
          <ol>
            <li>Kick + overheads em mono.</li>
            <li>Inverta polaridade se o low‑end cair.</li>
            <li>Alinhe os transientes.</li>
            <li>Repita com snare e room.</li>
          </ol>
        </section>

        <section id="errores-comunes" className="scroll-mt-24">
          <h2>Erros comuns</h2>
          <ul>
            <li>Confiar só na forma de onda.</li>
            <li>Alinhar tudo sem considerar groove.</li>
            <li>Esquecer a polaridade.</li>
          </ul>
        </section>

        <section id="checklist" className="scroll-mt-24">
          <h2>Checklist</h2>
          <ul>
            <li>Correlação estável e positiva.</li>
            <li>Low‑end sólido em mono.</li>
            <li>Transientes claros.</li>
          </ul>
        </section>
      </>
    ),
    "control-resonancias-stems": (
      <>
        <p>
          Ressonâncias são picos estreitos que deixam a faixa áspera. Use cortes
          cirúrgicos para manter o timbre.
        </p>

        <section id="que-son-resonancias" className="scroll-mt-24">
          <h2>O que são ressonâncias</h2>
          <p>Acúmulos de energia em bandas muito específicas.</p>
        </section>

        <section id="por-que-problema" className="scroll-mt-24">
          <h2>Por que é um problema</h2>
          <ul>
            <li>Fadiga auditiva.</li>
            <li>Mascaramento de elementos principais.</li>
            <li>Força a baixar o volume geral.</li>
          </ul>
        </section>

        <section id="como-detectar" className="scroll-mt-24">
          <h2>Como detectar</h2>
          <ol>
            <li>Use analisador e encontre picos estreitos.</li>
            <li>Faça sweep com Q alto.</li>
            <li>Corte 2‑4 dB nos picos.</li>
          </ol>
        </section>

        <section id="como-lo-hace-piroola" className="scroll-mt-24">
          <h2>Como a Piroola faz</h2>
          <p>
            <strong>S4_STEM_RESONANCE_CONTROL.py</strong> reduz ressonâncias e
            <strong> S4_STEM_HPF_LPF.py</strong> limpa extremos.
          </p>
        </section>

        <section id="workflow-manual" className="scroll-mt-24">
          <h2>Workflow manual</h2>
          <ol>
            <li>EQ paramétrico antes da compressão.</li>
            <li>Varredura com Q alto.</li>
            <li>EQ dinâmica se o pico for intermitente.</li>
          </ol>
        </section>

        <section id="errores-comunes" className="scroll-mt-24">
          <h2>Erros comuns</h2>
          <ul>
            <li>Cortes largos demais.</li>
            <li>Remover o caráter do som.</li>
            <li>Corrigir depois da compressão.</li>
          </ul>
        </section>

        <section id="checklist" className="scroll-mt-24">
          <h2>Checklist</h2>
          <ul>
            <li>Menos aspereza sem perder presença.</li>
            <li>Cortes estreitos e controlados.</li>
            <li>Dinâmica preservada.</li>
          </ul>
        </section>
      </>
    ),
    "lufs-true-peak-loudness": (
      <>
        <p>
          Aumentar loudness é fácil limitando demais, mas o mix fica plano. LUFS
          e true peak ajudam a subir o volume com qualidade.
        </p>

        <section id="que-son-lufs" className="scroll-mt-24">
          <h2>O que significa LUFS</h2>
          <p>LUFS mede a loudness percebida ao longo do tempo.</p>
        </section>

        <section id="targets-streaming" className="scroll-mt-24">
          <h2>Targets de streaming</h2>
          <ul>
            <li>-14 LUFS como referência comum.</li>
            <li>-1 dBTP para evitar distorção em codec.</li>
          </ul>
        </section>

        <section id="true-peak" className="scroll-mt-24">
          <h2>True peak</h2>
          <p>Intersample peaks passam de 0 dBFS na reconstrução.</p>
        </section>

        <section id="como-lo-hace-piroola" className="scroll-mt-24">
          <h2>Como a Piroola faz</h2>
          <p>
            <strong>S9_MASTER_GENERIC.py</strong> prepara a limitação final e
            <strong> S10_MASTER_FINAL_LIMITS.py</strong> verifica LUFS e true
            peak.
          </p>
        </section>

        <section id="paso-a-paso" className="scroll-mt-24">
          <h2>Passo a passo</h2>
          <ol>
            <li>Meça LUFS e true peak.</li>
            <li>Ceiling entre -1 e -0,5 dBTP.</li>
            <li>Ajuste threshold até o LUFS alvo.</li>
            <li>Escute pumping ou distorção.</li>
          </ol>
        </section>

        <section id="errores-comunes" className="scroll-mt-24">
          <h2>Erros comuns</h2>
          <ul>
            <li>Limitar demais e perder transientes.</li>
            <li>Ignorar true peak.</li>
            <li>Forçar targets inadequados ao gênero.</li>
          </ul>
        </section>

        <section id="checklist" className="scroll-mt-24">
          <h2>Checklist</h2>
          <ul>
            <li>LUFS integrados dentro da meta.</li>
            <li>True peak abaixo do teto seguro.</li>
            <li>Dinâmica preservada.</li>
          </ul>
        </section>
      </>
    ),
  },
  ja: {
    "como-eliminar-dc-offset-en-stems": (
      <>
        <p>
          DCオフセットは耳では気づきにくい問題ですが、メーターやコンプレッサー、
          そしてヘッドルームに大きく影響します。ステムがゼロからずれていると、
          ダイナミクス処理が不安定になります。
        </p>

        <section id="que-es-el-dc-offset" className="scroll-mt-24">
          <h2>DCオフセットとは</h2>
          <p>
            デジタル音声は0を中心に振れるべきです。DCオフセットは波形が上下に
            ずれて平均値が固定された状態で、コンバーターやプラグインの
            キャリブレーション不良が原因になります。
          </p>
          <ul>
            <li>ほぼ0Hzの超低域エネルギー。</li>
            <li>音楽的な情報はない。</li>
            <li>ヘッドルームを奪いダイナミクスを乱す。</li>
          </ul>
        </section>

        <section id="por-que-importa" className="scroll-mt-24">
          <h2>ステムで問題になる理由</h2>
          <ul>
            <li>ミックスバスのヘッドルームが減る。</li>
            <li>コンプやリミッターが過剰に反応する。</li>
            <li>低域の明瞭さが失われる。</li>
            <li>非対称な歪みが発生しやすい。</li>
          </ul>
        </section>

        <section id="como-detectarlo" className="scroll-mt-24">
          <h2>素早い検出方法</h2>
          <ol>
            <li>DCメーターで平均値を確認。</li>
            <li>波形をズームして中心が0か見る。</li>
            <li>平均値が~0でなければオフセットあり。</li>
          </ol>
        </section>

        <section id="como-lo-hace-piroola" className="scroll-mt-24">
          <h2>Piroolaでの処理</h2>
          <p>
            <strong>S1_STEM_DC_OFFSET.py</strong>がDCオフセットとピークを測定し、
            閾値(<code>dc_offset_max_db</code>)を超える場合は平均値を全サンプル
            から差し引きます。
          </p>
          <ul>
            <li>モノで測定して精度を確保。</li>
            <li>必要な場合のみ補正。</li>
            <li>クリーンなステムを書き戻し。</li>
          </ul>
        </section>

        <section id="solucion-manual" className="scroll-mt-24">
          <h2>安全な手動修正</h2>
          <ol>
            <li>DC除去プラグインまたはHPFを使用。</li>
            <li>20Hz付近から緩やかな傾斜で開始。</li>
            <li>波形が中央に戻るか確認。</li>
            <li>ノーマライズなしで書き出し。</li>
          </ol>
        </section>

        <section id="checklist" className="scroll-mt-24">
          <h2>チェックリスト</h2>
          <ul>
            <li>24‑bitまたは32‑float。</li>
            <li>クリッピングなし。</li>
            <li>冒頭/末尾の無音が整理されている。</li>
            <li>DCオフセットが安全範囲。</li>
          </ul>
        </section>

        <section id="faq" className="scroll-mt-24">
          <h2>FAQ</h2>
          <h3>DCオフセットは聞こえますか？</h3>
          <p>通常は聞こえませんが、ヘッドルームに影響します。</p>
          <h3>HPFで代用できますか？</h3>
          <p>一部は可能ですが、DC除去の方が正確です。</p>
        </section>
      </>
    ),
    "compresion-bus-bateria-punch-glue": (
      <>
        <p>
          ドラムバスのコンプレッションはキットを一体化させます。やり過ぎると
          トランジェントが失われるため、適切な設定が重要です。
        </p>

        <section id="por-que-bus" className="scroll-mt-24">
          <h2>なぜドラムバスを圧縮するのか</h2>
          <ul>
            <li>キックとスネアのまとまりを強化。</li>
            <li>ピークを抑えつつグルーヴ維持。</li>
            <li>ミックス全体に馴染ませる。</li>
          </ul>
        </section>

        <section id="crest-factor" className="scroll-mt-24">
          <h2>クレストファクター</h2>
          <p>6〜10 dBが一般的な目安です。</p>
        </section>

        <section id="ajustes-base" className="scroll-mt-24">
          <h2>基本設定</h2>
          <ul>
            <li>Ratio 2:1〜4:1（3:1が目安）。</li>
            <li>Attack 10〜30 ms、Release 100〜200 ms。</li>
            <li>平均GRは1〜3 dB。</li>
          </ul>
        </section>

        <section id="como-lo-hace-piroola" className="scroll-mt-24">
          <h2>Piroolaでの処理</h2>
          <p>
            <strong>S5_BUS_DYNAMICS_DRUMS.py</strong>がcrest factorを計測し、
            必要に応じてグルーコンプを適用します。
          </p>
        </section>

        <section id="paso-a-paso" className="scroll-mt-24">
          <h2>手動手順</h2>
          <ol>
            <li>ドラムを専用バスにルーティング。</li>
            <li>3:1、Attack 10 ms。</li>
            <li>1〜3 dBのGRを狙う。</li>
            <li>Releaseをテンポに合わせる。</li>
          </ol>
        </section>

        <section id="errores-comunes" className="scroll-mt-24">
          <h2>よくあるミス</h2>
          <ul>
            <li>Attackが速すぎる。</li>
            <li>Releaseが短すぎる。</li>
            <li>GRが大きすぎる。</li>
          </ul>
        </section>

        <section id="checklist" className="scroll-mt-24">
          <h2>チェックリスト</h2>
          <ul>
            <li>GRは1〜3 dB。</li>
            <li>トランジェントが残っている。</li>
          </ul>
        </section>
      </>
    ),
    "alineacion-fase-bateria-multimic": (
      <>
        <p>
          マルチマイク録音では小さな遅れでも位相キャンセルが起こります。キックの
          重さが消える場合は位相調整が必要です。
        </p>

        <section id="sintomas-fase" className="scroll-mt-24">
          <h2>症状</h2>
          <ul>
            <li>オーバーヘッド追加で低域が消える。</li>
            <li>ルームマイクでスネアが薄くなる。</li>
            <li>モノの方が良く聞こえる。</li>
          </ul>
        </section>

        <section id="por-que-se-pierde" className="scroll-mt-24">
          <h2>位相ずれの原因</h2>
          <ul>
            <li>マイク距離の差。</li>
            <li>極性反転。</li>
            <li>レイテンシ未補正。</li>
          </ul>
        </section>

        <section id="como-medir" className="scroll-mt-24">
          <h2>測定と整列方法</h2>
          <ol>
            <li>モノでキャンセルを確認。</li>
            <li>相関メーターで確認。</li>
            <li>極性を反転して比較。</li>
            <li>トランジェントをサンプル単位で合わせる。</li>
          </ol>
        </section>

        <section id="como-lo-hace-piroola" className="scroll-mt-24">
          <h2>Piroolaでの処理</h2>
          <p>
            <strong>S2_GROUP_PHASE_DRUMS.py</strong>が相関を分析し、タイミングと
            極性を最適化します。
          </p>
        </section>

        <section id="paso-a-paso" className="scroll-mt-24">
          <h2>手動ワークフロー</h2>
          <ol>
            <li>キック+オーバーヘッドをモノで確認。</li>
            <li>必要なら極性反転。</li>
            <li>トランジェントを揃える。</li>
            <li>スネアとルームでも同様に。</li>
          </ol>
        </section>

        <section id="errores-comunes" className="scroll-mt-24">
          <h2>よくあるミス</h2>
          <ul>
            <li>波形だけに頼る。</li>
            <li>グルーヴを無視して整列。</li>
            <li>極性チェックを忘れる。</li>
          </ul>
        </section>

        <section id="checklist" className="scroll-mt-24">
          <h2>チェックリスト</h2>
          <ul>
            <li>相関が安定している。</li>
            <li>モノで低域が残る。</li>
          </ul>
        </section>
      </>
    ),
    "control-resonancias-stems": (
      <>
        <p>
          共振は細いピークとして現れ、音を刺々しくします。広いEQではなく
          外科的なカットが必要です。
        </p>

        <section id="que-son-resonancias" className="scroll-mt-24">
          <h2>共振とは</h2>
          <p>部屋や楽器由来の特定周波数の盛り上がりです。</p>
        </section>

        <section id="por-que-problema" className="scroll-mt-24">
          <h2>問題になる理由</h2>
          <ul>
            <li>耳が疲れやすくなる。</li>
            <li>重要要素をマスクする。</li>
            <li>全体音量を下げる原因。</li>
          </ul>
        </section>

        <section id="como-detectar" className="scroll-mt-24">
          <h2>検出方法</h2>
          <ol>
            <li>アナライザーで狭いピークを探す。</li>
            <li>EQスイープで確認。</li>
            <li>2〜4 dBカット。</li>
          </ol>
        </section>

        <section id="como-lo-hace-piroola" className="scroll-mt-24">
          <h2>Piroolaでの処理</h2>
          <p>
            <strong>S4_STEM_RESONANCE_CONTROL.py</strong>が共振を抑え、
            <strong> S4_STEM_HPF_LPF.py</strong>で帯域整理します。
          </p>
        </section>

        <section id="workflow-manual" className="scroll-mt-24">
          <h2>手動ワークフロー</h2>
          <ol>
            <li>コンプ前にパラEQ。</li>
            <li>Q高めでスイープ。</li>
            <li>必要ならダイナミックEQ。</li>
          </ol>
        </section>

        <section id="errores-comunes" className="scroll-mt-24">
          <h2>よくあるミス</h2>
          <ul>
            <li>カットが広すぎる。</li>
            <li>キャラクターを削りすぎる。</li>
          </ul>
        </section>

        <section id="checklist" className="scroll-mt-24">
          <h2>チェックリスト</h2>
          <ul>
            <li>刺々しさが減っている。</li>
            <li>ダイナミクスが保たれている。</li>
          </ul>
        </section>
      </>
    ),
    "lufs-true-peak-loudness": (
      <>
        <p>
          リミッターで無理に上げると平坦になります。LUFSとTrue Peakを理解して
          クリーンに音量を上げましょう。
        </p>

        <section id="que-son-lufs" className="scroll-mt-24">
          <h2>LUFSとは</h2>
          <p>LUFSは聴感ラウドネスの指標です。</p>
        </section>

        <section id="targets-streaming" className="scroll-mt-24">
          <h2>配信の目標値</h2>
          <ul>
            <li>-14 LUFSが一般的な参考値。</li>
            <li>-1 dBTPで安全マージン。</li>
          </ul>
        </section>

        <section id="true-peak" className="scroll-mt-24">
          <h2>True Peak</h2>
          <p>インターサンプルピークを避けるために必要です。</p>
        </section>

        <section id="como-lo-hace-piroola" className="scroll-mt-24">
          <h2>Piroolaでの処理</h2>
          <p>
            <strong>S9_MASTER_GENERIC.py</strong>でリミット準備を行い、
            <strong> S10_MASTER_FINAL_LIMITS.py</strong>でLUFSとTrue Peakを確認。
          </p>
        </section>

        <section id="paso-a-paso" className="scroll-mt-24">
          <h2>手動手順</h2>
          <ol>
            <li>LUFS/True Peakを測定。</li>
            <li>Ceilingを-1〜-0.5 dBTPに設定。</li>
            <li>Thresholdで目標LUFSに調整。</li>
          </ol>
        </section>

        <section id="errores-comunes" className="scroll-mt-24">
          <h2>よくあるミス</h2>
          <ul>
            <li>リミットしすぎてトランジェントが消える。</li>
            <li>True Peakを無視する。</li>
          </ul>
        </section>

        <section id="checklist" className="scroll-mt-24">
          <h2>チェックリスト</h2>
          <ul>
            <li>目標LUFSに収まっている。</li>
            <li>True Peakが安全範囲。</li>
            <li>ダイナミクスが残っている。</li>
          </ul>
        </section>
      </>
    ),
  },
  zh: {
    "como-eliminar-dc-offset-en-stems": (
      <>
        <p>
          DC偏移是“听不见”的问题，但会影响电平、压缩器和整体余量。分轨如果带有
          固定偏移，混音总线从一开始就少了空间，动态处理也会不稳定。
        </p>

        <section id="que-es-el-dc-offset" className="scroll-mt-24">
          <h2>什么是DC偏移</h2>
          <p>
            数字音频应围绕0振荡。DC偏移是波形整体上移或下移，像有固定平均值。
            常见原因包括转换器、插件校准问题或导出错误。
          </p>
          <ul>
            <li>接近0 Hz的极低频能量。</li>
            <li>不包含音乐信息。</li>
            <li>占用余量并影响动态。</li>
          </ul>
        </section>

        <section id="por-que-importa" className="scroll-mt-24">
          <h2>为什么重要</h2>
          <ul>
            <li>混音总线余量变小。</li>
            <li>压缩/限制器更激进。</li>
            <li>低频清晰度下降。</li>
            <li>更容易产生非对称失真。</li>
          </ul>
        </section>

        <section id="como-detectarlo" className="scroll-mt-24">
          <h2>如何快速检测</h2>
          <ol>
            <li>使用DC表或显示平均值的分析器。</li>
            <li>放大波形查看是否居中。</li>
            <li>平均值不是~0就有偏移。</li>
          </ol>
        </section>

        <section id="como-lo-hace-piroola" className="scroll-mt-24">
          <h2>Piroola如何处理</h2>
          <p>
            <strong>S1_STEM_DC_OFFSET.py</strong>测量DC偏移和峰值，超过阈值
            (<code>dc_offset_max_db</code>)时，会从所有采样中减去平均值。
          </p>
          <ul>
            <li>单声道测量更稳定。</li>
            <li>只在需要时修正。</li>
            <li>重写为干净的分轨。</li>
          </ul>
        </section>

        <section id="solucion-manual" className="scroll-mt-24">
          <h2>手动安全修复</h2>
          <ol>
            <li>使用DC移除插件或带HPF的EQ。</li>
            <li>20 Hz起步，坡度柔和。</li>
            <li>确认波形回到中心。</li>
            <li>导出时不做归一化/限制。</li>
          </ol>
        </section>

        <section id="checklist" className="scroll-mt-24">
          <h2>检查清单</h2>
          <ul>
            <li>24‑bit或32‑float文件。</li>
            <li>无可见削波。</li>
            <li>开头/结尾静音干净。</li>
            <li>DC偏移已修正或在安全范围。</li>
          </ul>
        </section>

        <section id="faq" className="scroll-mt-24">
          <h2>常见问题</h2>
          <h3>DC偏移能听到吗？</h3>
          <p>通常听不见，但会影响余量与动态处理。</p>
          <h3>HPF能替代DC移除吗？</h3>
          <p>只能部分替代，DC移除更精确。</p>
        </section>
      </>
    ),
    "compresion-bus-bateria-punch-glue": (
      <>
        <p>
          鼓组总线压缩让鼓更“粘”。过度压缩会丢失瞬态和冲击力。下面是可复现的做法。
        </p>

        <section id="por-que-bus" className="scroll-mt-24">
          <h2>为什么压缩鼓组总线</h2>
          <ul>
            <li>强化kick/snare/overheads的一致性。</li>
            <li>控制峰值而不破坏节奏感。</li>
            <li>让鼓更好地融入整体。</li>
          </ul>
        </section>

        <section id="crest-factor" className="scroll-mt-24">
          <h2>Crest factor与动态</h2>
          <p>常见范围是6‑10 dB，具体取决于风格。</p>
        </section>

        <section id="ajustes-base" className="scroll-mt-24">
          <h2>基础设置</h2>
          <ul>
            <li>Ratio 2:1‑4:1（3:1为常用起点）。</li>
            <li>Attack 10‑30 ms，Release 100‑200 ms。</li>
            <li>平均GR 1‑3 dB。</li>
          </ul>
        </section>

        <section id="como-lo-hace-piroola" className="scroll-mt-24">
          <h2>Piroola如何处理</h2>
          <p>
            <strong>S5_BUS_DYNAMICS_DRUMS.py</strong>计算crest factor，必要时
            应用总线胶水压缩。
          </p>
        </section>

        <section id="paso-a-paso" className="scroll-mt-24">
          <h2>手动步骤</h2>
          <ol>
            <li>将鼓组路由到独立总线。</li>
            <li>3:1，Attack 10 ms。</li>
            <li>峰值削减1‑3 dB。</li>
            <li>Release与节奏呼吸。</li>
          </ol>
        </section>

        <section id="errores-comunes" className="scroll-mt-24">
          <h2>常见错误</h2>
          <ul>
            <li>Attack过快，瞬态被压扁。</li>
            <li>Release过短，出现泵感。</li>
            <li>平均GR过大。</li>
          </ul>
        </section>

        <section id="checklist" className="scroll-mt-24">
          <h2>检查清单</h2>
          <ul>
            <li>GR保持在1‑3 dB。</li>
            <li>瞬态仍清晰。</li>
          </ul>
        </section>
      </>
    ),
    "alineacion-fase-bateria-multimic": (
      <>
        <p>
          多麦鼓组中轻微的时间差就会导致相位抵消，踢鼓变弱、军鼓发空。下面是对齐方法。
        </p>

        <section id="sintomas-fase" className="scroll-mt-24">
          <h2>相位问题的症状</h2>
          <ul>
            <li>加overheads后低频消失。</li>
            <li>room mics打开后军鼓变空。</li>
            <li>mono听起来更好。</li>
          </ul>
        </section>

        <section id="por-que-se-pierde" className="scroll-mt-24">
          <h2>相位偏移的原因</h2>
          <ul>
            <li>麦克风距离不同。</li>
            <li>极性反转。</li>
            <li>延迟未补偿。</li>
          </ul>
        </section>

        <section id="como-medir" className="scroll-mt-24">
          <h2>如何测量与对齐</h2>
          <ol>
            <li>先在mono中定位抵消。</li>
            <li>查看相关性表。</li>
            <li>测试极性反转。</li>
            <li>按采样对齐瞬态。</li>
          </ol>
        </section>

        <section id="como-lo-hace-piroola" className="scroll-mt-24">
          <h2>Piroola如何处理</h2>
          <p>
            <strong>S2_GROUP_PHASE_DRUMS.py</strong>分析相关性并校正时间与极性。
          </p>
        </section>

        <section id="paso-a-paso" className="scroll-mt-24">
          <h2>手动流程</h2>
          <ol>
            <li>Kick+overheads切换到mono。</li>
            <li>必要时反转极性。</li>
            <li>对齐主瞬态。</li>
            <li>对snare和room重复。</li>
          </ol>
        </section>

        <section id="errores-comunes" className="scroll-mt-24">
          <h2>常见错误</h2>
          <ul>
            <li>只看波形不听耳朵。</li>
            <li>不考虑groove直接对齐。</li>
            <li>忘记先检查极性。</li>
          </ul>
        </section>

        <section id="checklist" className="scroll-mt-24">
          <h2>检查清单</h2>
          <ul>
            <li>相关性稳定且为正。</li>
            <li>mono低频扎实。</li>
          </ul>
        </section>
      </>
    ),
    "control-resonancias-stems": (
      <>
        <p>
          共振是窄带峰值，会让声音刺耳。需要用外科式EQ处理，而不是宽频削减。
        </p>

        <section id="que-son-resonancias" className="scroll-mt-24">
          <h2>什么是共振</h2>
          <p>来自房间、乐器或麦克风的频段能量堆积。</p>
        </section>

        <section id="por-que-problema" className="scroll-mt-24">
          <h2>为什么是问题</h2>
          <ul>
            <li>听感疲劳。</li>
            <li>掩蔽重要元素。</li>
            <li>需要降低整体音量。</li>
          </ul>
        </section>

        <section id="como-detectar" className="scroll-mt-24">
          <h2>如何检测</h2>
          <ol>
            <li>用分析器找窄峰。</li>
            <li>高Q扫频定位。</li>
            <li>削减2‑4 dB。</li>
          </ol>
        </section>

        <section id="como-lo-hace-piroola" className="scroll-mt-24">
          <h2>Piroola如何处理</h2>
          <p>
            <strong>S4_STEM_RESONANCE_CONTROL.py</strong>抑制共振，
            <strong> S4_STEM_HPF_LPF.py</strong>清理频谱边缘。
          </p>
        </section>

        <section id="workflow-manual" className="scroll-mt-24">
          <h2>手动流程</h2>
          <ol>
            <li>压缩前插入参数EQ。</li>
            <li>高Q扫频定位峰值。</li>
            <li>必要时使用动态EQ。</li>
          </ol>
        </section>

        <section id="errores-comunes" className="scroll-mt-24">
          <h2>常见错误</h2>
          <ul>
            <li>切得太宽导致音色变薄。</li>
            <li>去掉了本该保留的角色。</li>
          </ul>
        </section>

        <section id="checklist" className="scroll-mt-24">
          <h2>检查清单</h2>
          <ul>
            <li>刺耳感减少但存在感仍在。</li>
            <li>动态未被破坏。</li>
          </ul>
        </section>
      </>
    ),
    "lufs-true-peak-loudness": (
      <>
        <p>
          过度限制可以快速变大声，但会让混音变平。理解LUFS和True Peak才能干净地提
          升响度。
        </p>

        <section id="que-son-lufs" className="scroll-mt-24">
          <h2>什么是LUFS</h2>
          <p>LUFS是衡量主观响度的指标。</p>
        </section>

        <section id="targets-streaming" className="scroll-mt-24">
          <h2>流媒体目标</h2>
          <ul>
            <li>-14 LUFS为常见参考。</li>
            <li>-1 dBTP用于编码安全。</li>
          </ul>
        </section>

        <section id="true-peak" className="scroll-mt-24">
          <h2>True Peak</h2>
          <p>插值峰值可能超过0 dBFS，因此需要True Peak控制。</p>
        </section>

        <section id="como-lo-hace-piroola" className="scroll-mt-24">
          <h2>Piroola如何处理</h2>
          <p>
            <strong>S9_MASTER_GENERIC.py</strong>准备最终限制，
            <strong> S10_MASTER_FINAL_LIMITS.py</strong>检查LUFS与True Peak。
          </p>
        </section>

        <section id="paso-a-paso" className="scroll-mt-24">
          <h2>手动步骤</h2>
          <ol>
            <li>测量LUFS与True Peak。</li>
            <li>Ceiling设为-1到-0.5 dBTP。</li>
            <li>降低阈值到目标LUFS。</li>
          </ol>
        </section>

        <section id="errores-comunes" className="scroll-mt-24">
          <h2>常见错误</h2>
          <ul>
            <li>过度限制导致瞬态消失。</li>
            <li>忽略True Peak。</li>
            <li>强行追求不合适的目标。</li>
          </ul>
        </section>

        <section id="checklist" className="scroll-mt-24">
          <h2>检查清单</h2>
          <ul>
            <li>LUFS在目标范围内。</li>
            <li>True Peak低于安全值。</li>
            <li>动态仍然存在。</li>
          </ul>
        </section>
      </>
    ),
  },
};

export function getBlogPostContent(slug: string, locale: BlogLocale) {
  return (
    blogPostContent[locale]?.[slug] ??
    blogPostContent[defaultBlogLocale]?.[slug] ??
    null
  );
}
