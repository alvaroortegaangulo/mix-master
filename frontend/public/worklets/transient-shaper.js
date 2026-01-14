class TransientShaperProcessor extends AudioWorkletProcessor {
  static get parameterDescriptors() {
    return [
      {
        name: "punch",
        defaultValue: 0,
        minValue: -1,
        maxValue: 1,
        automationRate: "k-rate",
      },
    ];
  }

  constructor() {
    super();
    this.fastEnv = 0;
    this.slowEnv = 0;
    this.fastAttack = Math.exp(-1 / (sampleRate * 0.001));
    this.fastRelease = Math.exp(-1 / (sampleRate * 0.05));
    this.slowAttack = Math.exp(-1 / (sampleRate * 0.01));
    this.slowRelease = Math.exp(-1 / (sampleRate * 0.2));
    this.fastAttackInv = 1 - this.fastAttack;
    this.fastReleaseInv = 1 - this.fastRelease;
    this.slowAttackInv = 1 - this.slowAttack;
    this.slowReleaseInv = 1 - this.slowRelease;
  }

  process(inputs, outputs, parameters) {
    const input = inputs[0];
    const output = outputs[0];
    if (!input || input.length === 0) {
      return true;
    }

    const channels = input.length;
    const frames = input[0].length;
    const punchValues = parameters.punch;
    const punchIsConstant = punchValues.length === 1;

    let fastEnv = this.fastEnv;
    let slowEnv = this.slowEnv;

    for (let i = 0; i < frames; i += 1) {
      let mono = 0;
      for (let ch = 0; ch < channels; ch += 1) {
        mono += input[ch][i];
      }
      mono = mono / channels;
      const rect = Math.abs(mono);

      if (rect > fastEnv) {
        fastEnv = this.fastAttack * fastEnv + this.fastAttackInv * rect;
      } else {
        fastEnv = this.fastRelease * fastEnv + this.fastReleaseInv * rect;
      }

      if (rect > slowEnv) {
        slowEnv = this.slowAttack * slowEnv + this.slowAttackInv * rect;
      } else {
        slowEnv = this.slowRelease * slowEnv + this.slowReleaseInv * rect;
      }

      const transient = Math.max(fastEnv - slowEnv, 0);
      const ratio = transient / (fastEnv + 1e-6);
      let punch = punchIsConstant ? punchValues[0] : punchValues[i];
      if (punch > 1) punch = 1;
      if (punch < -1) punch = -1;
      const gain = 1 + punch * ratio;

      for (let ch = 0; ch < channels; ch += 1) {
        output[ch][i] = input[ch][i] * gain;
      }
    }

    this.fastEnv = fastEnv;
    this.slowEnv = slowEnv;
    return true;
  }
}

registerProcessor("transient-shaper", TransientShaperProcessor);
