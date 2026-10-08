struct Account {
    owner: String,
    balance: i64,
}

fn withdraw(acc: &Account, amount: i64) -> Result<i64, String> {
    if amount > acc.balance {
        return Err("not enough money".to_string());
    }
    Ok(acc.balance - amount)
}

fn main() {
    let mine = Account { owner: "Asha".to_string(), balance: 100 };
    match withdraw(&mine, 30) {
        Ok(left) => println!("Left: {}", left),
        Err(why) => println!("Error: {}", why),
    }
}
