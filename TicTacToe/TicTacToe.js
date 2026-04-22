let gameover = new Audio("TicTacToe_Asset/GameOver.mp3")
let TurnSound = new Audio("TicTacToe_Asset/Turn.mp3")
let resetSound = new Audio("TicTacToe_Asset/Reset.mp3")
let turn = "X";
let isGameOver = false;


// change the turn to the next player
const changeTurn = () => {
    return turn==="X"?turn="O":turn="X" 
}
// check if any player win or not
const checkWin = () => {
    let boxText = document.getElementsByClassName("boxContent");
    let wins = [
        [0, 1, 2],
        [3, 4, 5],
        [6, 7, 8],
        [0, 3, 6],
        [1, 4, 7],
        [2, 5, 8],
        [0, 4, 8],
        [2, 4, 6],
    ]

    wins.forEach(e => {
        if (boxText[e[0]].innerText === boxText[e[1]].innerText && boxText[e[2]].innerText === boxText[e[1]].innerText && boxText[e[0]].innerText !== "") {
            //converts the color of grid to green to show the winner.
            boxText[e[0]].parentElement.style.backgroundColor = "lightgreen";
            boxText[e[1]].parentElement.style.backgroundColor = "lightgreen";
            boxText[e[2]].parentElement.style.backgroundColor = "lightgreen";

            isGameOver = true;
            document.querySelector(".info").textContent = `${boxText[e[0]].innerText} Won`;
            gameover.play()     
            document.querySelector(".gameInfo").getElementsByTagName("img")[0].style.width="200px"
        }
    })
}


// game logic

let boxes = document.getElementsByClassName("box");
Array.from(boxes).forEach(element => {
    let boxText = element.querySelector(".boxContent");
    element.addEventListener('click', () => {
        if (boxText.textContent==="") {
            boxText.textContent = turn;
            TurnSound.play();
            changeTurn();
            checkWin();
            if (!isGameOver) {    
                document.querySelector(".info").textContent = `Player ${turn} turn`;
            }
        }
    })
})


// setting reset
document.getElementById("reset").addEventListener("click", () => {
    let allBoxText = document.getElementsByClassName("boxContent");   
    Array.from(allBoxText).forEach((element)=> {
        element.innerHTML = "";
        element.parentElement.style.backgroundColor = "white";

    })

    resetSound.play()
    document.querySelector(".gameInfo").getElementsByTagName("img")[0].style.width = "0px"
    isGameOver = false;
    document.querySelector(".info").textContent = `Player X turn`;
    turn = 'X';
})