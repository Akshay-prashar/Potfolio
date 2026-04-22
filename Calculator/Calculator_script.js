let string = "";
let buttons = document.querySelectorAll(".inpt-btn");
Array.from(buttons).forEach((button) => {
    button.addEventListener("click", (e) => {
        if (e.target.innerHTML=="=") {
            string = eval(string);
            document.querySelector(".input-box").value = string;
        }
        else if (e.target.innerHTML=='Ac') {
            string = '';
            document.querySelector(".input-box").value = string;
        }
        else {
            string = string + e.target.innerHTML;
            document.querySelector(".input-box").value = string;
        }
    })
})
