class MyComponent extends HTMLElement {
  constructor() {
    super();
    // Создаем Shadow DOM для изоляции стилей
    const shadow = this.attachShadow({ mode: 'open' });
    shadow.innerHTML = `
    <style>
    div.logo-container {
    position: relative;
    width: 347px;
    height: 46px;
    overflow: hidden;
}

div.first-icon-container{
    position: absolute;

    top: 10px;
    left: 10px;
    width: 36px;
    height: 36px;
    border-radius: 10px;
    background-color:#F6B3D3;
    z-index: 1;}

div.second-icon-container{
    position: absolute;
    top: 28px;
    left: 16px;
    width: 24.75px;
    height: 24.75px;
    border-radius: 10px;
    background-color:#292949;
    opacity: 0.08;
    z-index: 2;
}
    
div.logo-text-container {
    position: absolute;
    left: 60px;
}


h2 {
    font-family: system-ui;
    font-weight: 400;
    font-style: Regular;
    font-size: 20px;
    line-height: 100%;
    letter-spacing: -0.75px;
    text-align: center;
    text-transform: uppercase;
    color: #292949;
}
    </style>
<div class="logo-container">

    <div class="first-icon-container"></div>
    <div class="second-icon-container"></div>
    
    <div class="logo-text-container">
        <h2>pass-port feedback</h2>
    </div>

</div>
</div>
    `;
}
}

customElements.define('logo-on-page', MyComponent);


class FooterComponent extends HTMLElement {
  constructor() {
    super();
    // Создаем Shadow DOM для изоляции стилей
    const shadow = this.attachShadow({ mode: 'open' });
    shadow.innerHTML = `    <style>
        div.footer-container {
            width: 100%;
            height: 128px;
            background-color: #F2F3F8;
            bottom: 0;
            left: 0;
            position: fixed;
            border-radius: 76px 76px 0px 0px;
        }

        div.footer-text-container {
            width: 100%;
            height: 38px;
            opacity: 1;
            display: flex;
            padding-top: 32px;
            padding-bottom: 32px;
            padding-left: 352px;
            padding-right: 352px;
            gap: 32px;
        }

        div.footer-child-container {
            display: flex;
            flex-direction: column
        }



        h1.logo {
            font-family: system-ui;
            font-weight: 400;
            font-style: Regular;
            font-size: 20px;
            line-height: 100%;
            letter-spacing: -0.75px;
            text-align: center;
            text-transform: uppercase;
        }

        h2.footer-default-text {
            font-family: system-ui;
            font-weight: 500;
            font-style: Medium;
            font-size: 16px;
            line-height: 112.00000000000001%;
            letter-spacing: -1%;
            color: #888C9D;
            margin-bottom: -5px;
        }

        a.footer-emphasized-text {
            font-family: system-ui;
            font-weight: 500;
            font-style: Medium;
            font-size: 16px;
            line-height: 112.00000000000001%;
            letter-spacing: -1%;
            text-decoration: underline;
            text-decoration-style: solid;
            text-decoration-thickness: 0%;
            text-decoration-skip-ink: auto;
            color: #888C9D;
            margin-top: 12px;
            margin-bottom: -3px;
        }
        #trademark {
            margin-left: -50px;
        }
    </style>
    <div class="footer-container">
        <div class="footer-text-container">
            <!-- <div class="footer-first_row">
                <h1 class="logo">pass-port feedback</h1>
                <h2 class="footer-default-text">Contact details omitted from this public snapshot</h2>
                <a class="footer-emphasized-text">Пользовательское соглашение</a>
                <h2 class="footer-default-text">Business address omitted from this public snapshot</h2>
                <h2 class="footer-default-text">© 2025 PASS-PORT BUSINESS</h2>

            </div>
            <div class="footer-second-row">
                <a class="footer-emphasized-text">Политика Конфедициальности</a>
                <h2 class="footer-default-text">Business address omitted from this public snapshot</h2>
            </div> -->


            <div class="footer-child-container">
                <h1 class="logo">pass-port feedback</h1>
            </div>

            <div class="footer-child-container">
                <h2 class="footer-default-text">Contact details omitted from this public snapshot</h2>
            </div>

            <div class="footer-child-container">
                <a class="footer-emphasized-text">Пользовательское соглашение</a>
                <a class="footer-emphasized-text">Политика Конфедициальности</a>
            </div>

            <div class="footer-child-container">
                <h2 class="footer-default-text">Business address omitted from this public snapshot</h2>
                <h2 class="footer-default-text">Business address omitted from this public snapshot</h2>
            </div>

            <div class="footer-child-container" id="footer-trademark">
                <h2 class="footer-default-text">© 2025 PASS-PORT BUSINESS</h2>
            </div>

        </div>
    </div>
    `;
}
}

customElements.define('footer-on-page', FooterComponent);