/*
 * Copyright (c) 2022 AtLarge Research
 *
 * Permission is hereby granted, free of charge, to any person obtaining a copy
 * of this software and associated documentation files (the "Software"), to deal
 * in the Software without restriction, including without limitation the rights
 * to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
 * copies of the Software, and to permit persons to whom the Software is
 * furnished to do so, subject to the following conditions:
 *
 * The above copyright notice and this permission notice shall be included in all
 * copies or substantial portions of the Software.
 *
 * THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
 * IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
 * FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
 * AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
 * LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
 * OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
 * SOFTWARE.
 */

import clsx from 'clsx'
import React from 'react'

import styles from './styles.module.css'
import OverviewImage from '@site/static/img/high-level-overview-dt-pt.png'

export default function HomepageInto() {
    return (
        <section id="intro" className={styles.intro}>
            <div className="container padding-vert--lg">
                <div className="row">
                    <div className={clsx('col col--5', styles.textCol)}>
                        <h3>Shadow Mode Digital Twin</h3>
                        <p>
                            OpenDT bridges physical and digital infrastructure through continuous monitoring and
                            simulation. A human-in-the-loop approach enables SLO-oriented steering of datacenter
                            operations.
                        </p>
                        <ul>
                            <li>Connect to real or mocked datacenters</li>
                            <li>Replay historical workloads at configurable speed</li>
                            <li>Compare predicted vs actual power in real-time</li>
                        </ul>
                    </div>
                    <div className={clsx('col col--5', styles.imageCol)}>
                        <img
                            src={OverviewImage}
                            alt="High-level overview: Physical ICT Infrastructure connected to Digital ICT Infrastructure through monitoring, datagen, and SLO-oriented steering with human in the loop"
                            className={styles.overviewImage}
                        />
                    </div>
                </div>
            </div>
        </section>
    )
}
